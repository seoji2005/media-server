"""Qwen boundary regressions and saved-job recovery; model-free fixtures unless noted."""
import copy
from contextlib import contextmanager
import hashlib
import io
import json
import os
import unittest
from unittest.mock import patch

from media_clarity import asr_checkpoints, gemini, qwen
from media_clarity.jobs import Jobs, execute, source_units
from media_clarity.storage import MediaError
from tests import test_gemini as fixtures


def unit(text, start, end, raw_start=None, raw_end=None):
    return {'text':text, 'start':start, 'end':end,
            'raw_start':start if raw_start is None else raw_start,
            'raw_end':end if raw_end is None else raw_end}


def evidence(text, units, language='Japanese'):
    return {'profile':qwen.LEGACY_PROFILE, 'language':language, 'text':text,
            'audio_sha256':'a'*64, 'units':units, 'boundary':'end'}


@contextmanager
def audio_file(audio):
    with io.BytesIO(audio.tobytes()) as stream:
        yield stream, len(audio)


class QwenBoundaryTests(unittest.TestCase):
    def handoff_fixture(self, profile=qwen.PROFILE):
        import numpy as np
        speech=object.__new__(qwen.QwenSpeech);speech.asr_profile=profile
        audio=np.ones(35*16000,dtype=np.float32)*.1
        first=evidence('前です。次へ帰っ',[unit('前',21,22),unit('です',22,23),
            unit('次',23.16,24.3),unit('へ',24.3,25.1),unit('帰っ',29.8,30)])
        following=evidence('次へ帰って、また帰って。',[unit('次',.08,.5),unit('へ',.5,.8),
            unit('帰って',1,2),unit('また',2.2,2.5),unit('帰って',2.5,3)])
        calls=[]
        def recognize(samples):
            calls.append(len(samples))
            rec=first if len(samples)==30*16000 else following
            return rec['text'],rec['language']
        def align(samples,text,language):
            return copy.deepcopy((first if text==first['text'] else following)['units'])
        return speech,audio,recognize,align,calls

    def test_handoff_reprocesses_suffix_and_keeps_raw_text_and_real_repetition(self):
        speech,audio,recognize,align,calls=self.handoff_fixture()
        with patch('media_clarity.qwen.decoded_audio',side_effect=lambda *args:audio_file(audio)), \
                patch.object(speech,'recognize',side_effect=recognize),patch.object(speech,'align',side_effect=align):
            parts=list(speech.transcribe_parts(None,35,0,[]))
        self.assertEqual([p['clip'] for p in parts],[[0,23.08],[23.08,35]])
        self.assertEqual(parts[0]['evidence']['recognition_end'],30)
        self.assertEqual(parts[0]['evidence']['text'],'前です。次へ帰っ')
        self.assertEqual([c['text'] for p in parts for c in p['cues']],['前です。','次へ帰って、','また帰って。'])
        self.assertEqual(calls,[480000,190720])
        for part in parts:self.assertEqual(asr_checkpoints.validate_part(part,35),part)

    def test_handoff_resume_checks_full_recognition_audio_and_reuses_committed_prefix(self):
        speech,audio,recognize,align,calls=self.handoff_fixture()
        with patch('media_clarity.qwen.decoded_audio',side_effect=lambda *args:audio_file(audio)), \
                patch.object(speech,'recognize',side_effect=recognize),patch.object(speech,'align',side_effect=align):
            generator=speech.transcribe_parts(None,35,0,[])
            saved=next(generator);generator.close();calls.clear()
            remaining=list(speech.transcribe_parts(None,35,0,[saved]))
            self.assertEqual(calls,[190720]);self.assertEqual(remaining[0]['clip'],[23.08,35])
            calls.clear();audio[29*16000]=.5  # Outside committed prefix, inside its recognition evidence.
            with self.assertRaisesRegex(MediaError,'processing_checkpoint_invalid'):
                list(speech.transcribe_parts(None,35,0,[saved]))
            self.assertEqual(calls,[])

    def test_handoff_rejects_changed_extent_or_derived_cues(self):
        speech,audio,recognize,align,_=self.handoff_fixture()
        with patch('media_clarity.qwen.decoded_audio',side_effect=lambda *args:audio_file(audio)), \
                patch.object(speech,'recognize',side_effect=recognize),patch.object(speech,'align',side_effect=align):
            generator=speech.transcribe_parts(None,35,0,[])
            part=next(generator);generator.close()
        for mutate in (lambda p:p['clip'].__setitem__(1,24),
                       lambda p:p['evidence'].__setitem__('recognition_end',36),
                       lambda p:p['cues'][0].__setitem__('text','changed')):
            bad=copy.deepcopy(part);mutate(bad)
            with self.assertRaisesRegex(MediaError,'processing_checkpoint_invalid'):
                asr_checkpoints.validate_part(bad,35)

    def test_legacy_windows_are_not_reinterpreted_as_handoffs(self):
        speech,audio,recognize,align,calls=self.handoff_fixture(qwen.LEGACY_PROFILE)
        with patch('media_clarity.qwen.decoded_audio',side_effect=lambda *args:audio_file(audio)), \
                patch.object(speech,'recognize',side_effect=recognize),patch.object(speech,'align',side_effect=align):
            parts=list(speech.transcribe_parts(None,35,0,[]))
            calls.clear();self.assertEqual(list(speech.transcribe_parts(None,35,0,parts)),[])
        self.assertEqual([p['clip'] for p in parts],[[0,30],[30,35]])
        self.assertNotIn('recognition_end',parts[0]['evidence']);self.assertEqual(calls,[])
        self.assertEqual(parts[0]['cues'][-1]['text'],'次へ帰っ')

    def test_handoff_requires_late_nonoverlapping_internal_phrase_and_forced_cut(self):
        cues=[{'start':19,'end':21,'text':'Finished.'},{'start':21.2,'end':29.9,'text':'unfinished'}]
        for boundary in ('quiet','end'):
            self.assertEqual(qwen.phrase_handoff(cues,[0,30],boundary),(30,cues))
        for change in ({'end':19.9},{'text':'unfinished'},{'end':21.3}):
            altered=copy.deepcopy(cues);altered[0].update(change)
            self.assertEqual(qwen.phrase_handoff(altered,[0,30],'forced'),(30,altered))

    def test_bounded_windows_cover_silence_and_continuous_audio_without_overlap(self):
        import numpy as np
        for quiet in (False, True):
            audio=np.ones(65*16000,dtype=np.float32)*.1
            if quiet:audio[24*16000:25*16000]=0
            plan=list(qwen.windows(audio))
            self.assertEqual(plan[0][0],0);self.assertEqual(plan[-1][1],len(audio))
            self.assertTrue(all(0 < end-start <= 30*16000 for start,end,_ in plan))
            self.assertTrue(all(a[1]==b[0] for a,b in zip(plan,plan[1:])))
            self.assertEqual(plan[0][2],'quiet' if quiet else 'forced')
            self.assertEqual(sum(end-start for start,end,_ in plan),len(audio))

    def test_gap_between_prefix_and_word_never_splits_congratulations(self):
        text = 'おめでとう。'
        record = evidence(text, [unit('お', .2, .4), unit('めでとう', 1.7, 2.3)])
        cues = qwen.validate_evidence(record, [0,3])
        self.assertEqual(cues,[{'start':.2,'end':2.3,'text':text}])
        self.assertEqual(source_units(cues,qwen.PROFILE),cues)

    def test_zero_length_phrase_keeps_text_with_neighbor_and_raw_timing(self):
        record = evidence('うん。え、次です。', [unit('うん',1,1,1,.7),unit('え',1,1),
            unit('次',1.1,1.4),unit('です',1.4,2)])
        cues,error = qwen.evidence_result(record,[0,3])
        self.assertIsNone(error)
        self.assertEqual(''.join(c['text'] for c in cues),record['text'])
        part={'clip':[0,3],'cues':cues,'evidence':record,'error':None}
        self.assertEqual(asr_checkpoints.validate_part(part,3)['evidence'],record)
        broken=copy.deepcopy(part);broken['cues'][0]['text']='失われた'
        with self.assertRaisesRegex(MediaError,'processing_checkpoint_invalid'):
            asr_checkpoints.validate_part(broken,3)

    def test_unrepresentable_text_is_persistable_but_not_ready(self):
        record=evidence('うん。え',[unit('うん',1,1),unit('え',1,1)])
        cues,error=qwen.evidence_result(record,[0,3])
        self.assertEqual((cues,error),([],'alignment_unresolved'))
        part={'clip':[0,3],'cues':cues,'evidence':record,'error':error}
        self.assertEqual(asr_checkpoints.validate_part(part,3),part)
        self.assertEqual(qwen.evidence_result(evidence('Hello',[unit('world',.1,.9)]),[0,3])[1],
                         'alignment_text_mismatch')
        self.assertEqual(qwen.evidence_result(evidence('Hello',[],'Thai'),[0,3])[1],
                         'alignment_language_unsupported')

    def test_source_spacing_punctuation_and_empty_speech(self):
        record=evidence('Hello, world!',[unit('Hello',.2,.7),unit('world',1,1.5)],'English')
        cues=qwen.validate_evidence(record,[2,5])
        self.assertEqual([c['text'] for c in cues],['Hello,','world!'])
        self.assertEqual(qwen.validate_evidence(evidence('',[],None),[0,3]),[])
        record['units'][0]['end']=float('nan')
        self.assertEqual(qwen.evidence_result(record,[0,3])[1],'alignment_unresolved')

    def test_native_alignment_symbols_keep_exact_dialogue(self):
        for text, words in [
                ('It costs $5.', ['It','costs','5']),
                ('I use C++.', ['I','use','C']),
                ('It is 20°C.', ['It','is','20C']),
                ('Brand™ works.', ['Brand','works']),
                ("Don't go.", ["Don't",'go'])]:
            with self.subTest(text=text):
                record=evidence(text,[unit(w,i*.3,i*.3+.2) for i,w in enumerate(words)],'English')
                cues=qwen.validate_evidence(record,[0,3])
                self.assertEqual([c['text'] for c in cues],[text])

    def test_japanese_normalization_keeps_source_symbols_and_composed_offsets(self):
        for text, words in [('２０℃です。',['20','C','です']),
                            ('Brand™です。',['BrandTM','です']),
                            ('カ\u3099です。',['ガ','です']),
                            ('İです。',['I','です'])]:
            with self.subTest(text=text):
                record=evidence(text,[unit(w,i*.3,i*.3+.2) for i,w in enumerate(words)])
                self.assertEqual(''.join(c['text'] for c in qwen.validate_evidence(record,[0,3])),text)

    def test_final_quantized_tick_is_bounded_without_losing_text_or_raw_times(self):
        record=evidence('みたいな。',[unit('みたい',4.5,4.96),unit('な',4.96,5.04)])
        cues=qwen.validate_evidence(record,[30,35])
        self.assertEqual(cues,[{'start':34.5,'end':35,'text':'みたいな。'}])
        self.assertEqual(record['units'][-1]['end'],5.04)
        record['units'][-1]['end']=5.2
        self.assertEqual(qwen.evidence_result(record,[30,35])[1],'alignment_unresolved')
        decimal=evidence('1.5です。',[unit('1',.1,.3),unit('5',.4,.6),unit('です',.7,1)])
        self.assertEqual(len(qwen.validate_evidence(decimal,[0,2])),1)

    def test_exact_schema_rejects_extra_context_id_without_retry(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic-key'}):
            backend=gemini.Gemini(gemini.CONFIG)
        bodies=[]
        def extra(body,key,model):
            bodies.append(body)
            return fixtures.response([{'id':'0','text':'축하해.'},{'id':'1','text':'문맥만'}])
        with patch('media_clarity.gemini.request',side_effect=extra),self.assertRaisesRegex(MediaError,'gemini_response_invalid'):
            backend.translate_context(['おめでとう。'],[('','context-only')])
        self.assertEqual(len(bodies),1)
        schema=bodies[0]['generationConfig']['responseSchema']['properties']['translations']
        self.assertEqual((schema['minItems'],schema['maxItems']),(1,1))
        self.assertEqual(schema['items']['properties']['id']['enum'],['0'])
        with patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic-key'}),patch('media_clarity.gemini.request',side_effect=fixtures.reply) as call:
            gemini.Gemini(gemini.FAITHFUL_V2).translate_context(['before'],[('','')])
        old=call.call_args.args[0]['generationConfig']['responseSchema']['properties']['translations']
        self.assertNotIn('minItems',old)
        self.assertNotEqual(gemini.identity(),gemini.identity(gemini.FAITHFUL_V2))


class QwenJobTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.GeminiJobTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.GeminiJobTests.tearDownClass.__func__)
    setUp=fixtures.GeminiJobTests.setUp
    tearDown=fixtures.GeminiJobTests.tearDown

    def queue(self,profile=qwen.PROFILE):
        with patch('media_clarity.qwen.local_models'):
            return self.jobs.enqueue(self.item['id'],force=True,provider='gemini',speech_profile=profile)

    def test_legacy_qwen_job_restores_its_backend_profile_and_text_spacing(self):
        class Speech:
            audio_timing='source-timestamps-v1'
            def __init__(self,root,profile):
                self.asr_profile=profile
                if profile != qwen.LEGACY_PROFILE:raise AssertionError('legacy profile changed')
            def identity(self):return 'synthetic-legacy-qwen'
            def close(self):pass
            def transcribe_parts(self,path,duration,index,saved):
                rec=evidence('前です。続きです。',[unit('前',.1,.3),unit('です',.3,.5),
                    unit('続き',.5,.7),unit('です',.7,1)])
                yield {'clip':[0,4],'cues':qwen.validate_evidence(rec,[0,4]),'evidence':rec,'error':None}
        jid=self.queue(qwen.LEGACY_PROFILE);self.jobs.action(jid,'pause')
        with patch('media_clarity.qwen.local_models'),patch('media_clarity.qwen.QwenSpeech',Speech), \
                patch('media_clarity.gemini.request',side_effect=fixtures.reply):
            self.jobs.action(jid,'resume');execute(self.store,jid)
        self.assertEqual(self.jobs.row(jid)['state'],'succeeded')
        track=self.jobs.status(self.item['id'])['tracks'][0]['id']
        new=self.jobs.retranslate(self.item['id'],track,'gemini')
        self.assertEqual(self.jobs.row(new)['speech_profile'],qwen.LEGACY_PROFILE)
        self.assertEqual(source_units(json.loads(self.jobs.row(new)['transcript']),qwen.LEGACY_PROFILE),
                         json.loads(self.jobs.row(new)['transcript']))

    def test_qwen_partial_resume_and_legacy_profile_survive_restart(self):
        class Speech:
            asr_profile=qwen.PROFILE
            audio_timing='source-timestamps-v1'
            calls=[]
            fail=True
            def __init__(self,root):pass
            def identity(self):return 'synthetic-qwen'
            def close(self):pass
            def transcribe_parts(self,path,duration,index,saved):
                for i in range(len(saved),2):
                    self.calls.append(i)
                    if i==1 and self.fail:raise MediaError('processing_interrupted',409)
                    rec=evidence('おめでとう。',[unit('お',.1,.2),unit('めでとう',1,1.5)])
                    clip=[i*2,i*2+2]
                    rec.update(profile=qwen.PROFILE,recognition_end=clip[1])
                    yield {'clip':clip,'cues':qwen.validate_evidence(rec,clip),'evidence':rec,'error':None}
        jid=self.queue()
        with patch('media_clarity.qwen.QwenSpeech',Speech),patch('media_clarity.gemini.request') as call:
            execute(self.store,jid)
        call.assert_not_called();self.assertEqual(self.jobs.row(jid)['asr_completed'],1)
        self.store.close();self.store.start();self.jobs=Jobs(self.store);Speech.fail=False
        with patch('media_clarity.qwen.local_models'),patch('media_clarity.qwen.QwenSpeech',Speech),patch('media_clarity.gemini.request',side_effect=fixtures.reply):
            self.jobs.action(jid,'resume');execute(self.store,jid)
        self.assertEqual(self.jobs.row(jid)['state'],'succeeded')
        self.assertEqual(Speech.calls,[0,1,1])
        track=self.jobs.status(self.item['id'])['tracks'][0]['id']
        new=self.jobs.retranslate(self.item['id'],track,'gemini')
        self.assertEqual(self.jobs.row(new)['speech_profile'],qwen.PROFILE)
        with patch('media_clarity.qwen.QwenSpeech',side_effect=AssertionError('ASR on retranslation')),patch('media_clarity.gemini.request',side_effect=fixtures.reply):
            execute(self.store,new)
        self.assertEqual(self.jobs.row(new)['state'],'succeeded')

    def test_unresolved_alignment_is_saved_and_sends_no_cloud_text(self):
        class Speech:
            asr_profile=qwen.PROFILE
            def __init__(self,root):pass
            def identity(self):return 'synthetic-unresolved'
            def close(self):pass
            def transcribe_parts(self,path,duration,index,saved):
                rec=evidence('うん。え',[unit('うん',1,1),unit('え',1,1)])
                rec.update(profile=qwen.PROFILE,recognition_end=3)
                yield {'clip':[0,3],'cues':[],'evidence':rec,'error':'alignment_unresolved'}
        jid=self.queue()
        with patch('media_clarity.qwen.QwenSpeech',Speech),patch('media_clarity.gemini.request') as call:
            execute(self.store,jid)
        call.assert_not_called()
        row=self.jobs.row(jid);self.assertEqual((row['state'],row['error']),('failed','alignment_unresolved'))
        self.assertEqual(asr_checkpoints.load(self.store,row,4)[0]['evidence']['text'],'うん。え')
        self.assertEqual(self.jobs.status(self.item['id'])['tracks'],[])

    def test_new_job_rejects_a_mislabelled_legacy_span_before_cloud_egress(self):
        class Speech:
            asr_profile=qwen.PROFILE
            def __init__(self,root):pass
            def identity(self):return 'synthetic-mixed-profiles'
            def close(self):pass
            def transcribe_parts(self,path,duration,index,saved):
                rec=evidence('はい。',[unit('はい',.1,.5)])
                yield {'clip':[0,4],'cues':qwen.validate_evidence(rec,[0,4]),'evidence':rec,'error':None}
        jid=self.queue()
        with patch('media_clarity.qwen.QwenSpeech',Speech),patch('media_clarity.gemini.request') as call:
            execute(self.store,jid)
        call.assert_not_called()
        self.assertEqual(self.jobs.row(jid)['error'],'processing_checkpoint_invalid')
        self.assertEqual(self.jobs.row(jid)['asr_completed'],0)
        self.assertEqual(self.jobs.status(self.item['id'])['tracks'],[])
