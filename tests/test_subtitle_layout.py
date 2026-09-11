"""Readability is bounded presentation, never destructive transcript editing."""
import copy
import unittest
from unittest.mock import patch

from media_clarity.storage import MediaError
from media_clarity.subtitles import parse_srt, webvtt
from media_clarity.subtitle_layout import generated_layout, width, FALLBACK


PARAGRAPH = ('그는 역에서 기다리던 친구에게 오늘 있었던 일을 차근차근 이야기했습니다. '
             '처음에는 작은 오해라고 생각했지만 서로의 설명을 듣고 나니 왜 그런 일이 '
             '벌어졌는지 이해할 수 있었습니다. 두 사람은 다음부터 중요한 약속은 '
             '미리 확인하기로 했습니다.')


class LayoutTests(unittest.TestCase):
    def test_long_korean_sentence_is_readable_without_changing_source_or_interval(self):
        source = [{'start':2.3,'end':13.3,'text':PARAGRAPH}]
        before = copy.deepcopy(source)
        result = generated_layout(source, 20)
        self.assertEqual(source,before)
        self.assertGreater(len(result['cues']),1)
        self.assertEqual(result['units'],[0]*len(result['cues']))
        self.assertEqual(result['cues'][0]['start'],2.3)
        self.assertEqual(result['cues'][-1]['end'],13.3)
        self.assertEqual(' '.join(c['text'] for c in result['cues']).split(),PARAGRAPH.split())
        previous = 2.3
        for cue in result['cues']:
            self.assertEqual(cue['start'],previous)
            self.assertLessEqual(len(cue['text'].splitlines()),2)
            self.assertTrue(all(width(line)<=16 for line in cue['text'].splitlines()))
            self.assertGreaterEqual(cue['end']-cue['start'],.833)
            self.assertLessEqual(cue['end']-cue['start'],7)
            previous = cue['end']
        self.assertEqual(result['issues'],[])
        self.assertTrue(all(len(c['text'].split())>1 for c in result['cues']))

    def test_impossible_speed_and_unbreakable_names_are_flagged_not_deleted(self):
        text='김' * 40 + ' 2026-10-11 부정하지 않았습니다.'
        result=generated_layout([{'start':0,'end':1,'text':text}],1)
        self.assertEqual(' '.join(c['text'] for c in result['cues']).split(),text.split())
        codes={c for issue in result['issues'] for c in issue['codes']}
        self.assertTrue({'line_length','reading_speed'} <= codes)
        self.assertEqual(result['cues'][-1]['end'],1)
        self.assertIn('김'*40,result['cues'][0]['text'])

    def test_fallback_labels_follow_every_split_and_count_towards_layout(self):
        source=[{'start':0,'end':11,'text':PARAGRAPH}, {'start':12,'end':14,'text':'새 자막.'}]
        result=generated_layout(source,14,{0})
        fallback={i for i,unit in enumerate(result['units']) if unit==0}
        output=webvtt(result['cues'],fallback)
        self.assertEqual(output.count('[원문]'),len(fallback))
        self.assertGreater(len(fallback),1)
        for i in fallback:
            self.assertTrue(all(width(line)<=16 for line in (FALLBACK+result['cues'][i]['text']).splitlines()))
        self.assertNotIn('[원문] 새 자막',output)

    def test_timing_constraints_rounding_gaps_and_existing_overlap_are_honest(self):
        source=[{'start':0,'end':.1,'text':'짧음.'},
                {'start':2,'end':17,'text':'이름'},
                {'start':16,'end':20,'text':'겹친 원래 발화.'}]
        result=generated_layout(source,20)
        self.assertEqual(result['cues'],[{**source[0],'end':.834},*source[1:]])
        codes={c for issue in result['issues'] for c in issue['codes']}
        self.assertTrue({'long_duration','source_overlap'}<=codes)
        self.assertNotIn('short_duration',codes)
        # Many differently sized words must never collapse or exceed outer bounds.
        for duration in (.001,.833,.834,1.668,7,11.999):
            with self.subTest(duration=duration):
                p=generated_layout([{'start':.001,'end':duration+.001,'text':PARAGRAPH}],duration+.001)
                self.assertEqual(p['cues'][0]['start'],.001)
                self.assertEqual(p['cues'][-1]['end'],round(duration+.001,3))
                self.assertTrue(all(c['start']<c['end'] for c in p['cues']))

    def test_half_width_accounting_and_unicode_words_survive(self):
        self.assertEqual(width('한글 A!'),3.5)
        self.assertEqual(width('é'),width('e\u0301'))
        text='가족 👩\u200d👩\u200d👧\u200d👦 이름 e\u0301 영어 ABC123.'
        p=generated_layout([{'start':0,'end':5,'text':text}],5)
        self.assertEqual(' '.join(c['text'] for c in p['cues']).split(),text.split())

    def test_overlapping_split_units_keep_time_order_content_and_warning_mapping(self):
        source=[{'start':0,'end':10,'text':PARAGRAPH},
                {'start':1,'end':1.1,'text':'짧음.'},
                {'start':1.2,'end':2,'text':'겹침.'}]
        p=generated_layout(source,10,{0})
        self.assertEqual([c['start'] for c in p['cues']],sorted(c['start'] for c in p['cues']))
        for unit,original in enumerate(source):
            children=[c for c,u in zip(p['cues'],p['units']) if u==unit]
            self.assertEqual(' '.join(c['text'] for c in children).split(),original['text'].split())
            self.assertEqual(children[0]['start'],original['start'])
            self.assertEqual(children[-1]['end'],original['end'])
        codes={issue['cue']:issue['codes'] for issue in p['issues']}
        self.assertIn('short_duration',codes[p['units'].index(1)])
        self.assertIn('source_overlap',codes[p['units'].index(2)])
        self.assertNotIn('short_duration',codes.get(0,[]))
        fallback={i for i,u in enumerate(p['units']) if u==0}
        vtt=webvtt(p['cues'],fallback)
        self.assertEqual(vtt.count('[원문]'),len(fallback))
        self.assertNotIn('[원문] 짧음.',vtt)

    def test_output_budget_preserves_all_units_instead_of_failing_job(self):
        cues=[{'start':i*10,'end':i*10+9,'text':PARAGRAPH} for i in range(8)]
        with patch('media_clarity.subtitle_layout.MAX_CUES',10):
            p=generated_layout(cues,80)
        self.assertLessEqual(len(p['cues']),10)
        self.assertEqual(set(p['units']),set(range(8)))
        for index in range(8):
            self.assertEqual(' '.join(c['text'] for c,u in zip(p['cues'],p['units']) if u==index).split(),PARAGRAPH.split())

    def test_short_cue_uses_only_a_full_available_reading_interval(self):
        source=[{'start':1,'end':1.08,'text':'응.'},
                {'start':1.834,'end':2.1,'text':'맞아.'},
                {'start':2.667,'end':3.667,'text':'출발하자.'}]
        before=copy.deepcopy(source)
        result=generated_layout(source,4)
        self.assertEqual(source,before)
        self.assertEqual(result['profile'],'ko-readable-v2')
        self.assertEqual(result['units'],[0,1,2])
        self.assertEqual(result['cues'],[{**source[0],'end':1.834},*source[1:]])
        # A gap one millisecond short of the minimum is left alone, not partially
        # stretched or hidden by removing the short-duration finding.
        issues={i['cue']:i['codes'] for i in result['issues']}
        self.assertNotIn(0,issues)
        self.assertIn('short_duration',issues[1])

    def test_video_boundary_and_overlapping_turns_block_short_cue_hold(self):
        # 1.001 * 1000 is 1000.9999999999999: do not floor an exact video end.
        exact=generated_layout([{'start':.167,'end':.247,'text':'끝.'}],1.001)
        self.assertEqual(exact['cues'][0]['end'],1.001)
        self.assertEqual(exact['issues'],[])
        for duration, expected in [(1.834,1.834),(1.8339,1.1)]:
            with self.subTest(duration=duration):
                p=generated_layout([{'start':1,'end':1.1,'text':'끝.'}],duration)
                self.assertEqual(p['cues'][0]['end'],expected)
        source=[{'start':0,'end':4,'text':'계속 이야기하는 중.'},
                {'start':1,'end':1.1,'text':'응.'},
                {'start':2,'end':2.2,'text':'네.'},
                {'start':3,'end':5,'text':'이어서 말해.'}]
        p=generated_layout(source,6)
        self.assertEqual(p['cues'],source)
        # The active interval is not just the immediately preceding short cue.
        issues={i['cue']:i['codes'] for i in p['issues']}
        for i in (1,2):
            self.assertIn('short_duration',issues[i])
            self.assertIn('source_overlap',issues[i])
        same_start=[{'start':1,'end':1.1,'text':'가.'},
                    {'start':1,'end':1.2,'text':'나.'}]
        self.assertEqual(generated_layout(same_start,3)['cues'],same_start)

    def test_held_cue_rechecks_speed_including_fallback_label(self):
        source=[{'start':0,'end':.1,'text':'반드시기억할내용'}]
        normal=generated_layout(source,2)
        fallback=generated_layout(source,2,{0})
        self.assertEqual(normal['cues'],fallback['cues'])
        self.assertEqual(normal['cues'][0]['end'],.834)
        self.assertEqual(normal['issues'],[])
        self.assertEqual(fallback['issues'],[{'cue':0,'codes':['reading_speed']}])
        self.assertIn('[원문] 반드시기억할내용',webvtt(fallback['cues'],{0}))


class CompatibleSrtTests(unittest.TestCase):
    def test_empty_body_and_consecutive_blank_separators_are_skipped(self):
        for separator in ('\n\n\n','\n \n\t\n','\r\n\r\n\r\n'):
            raw=('1\n0:00:00,000 --> 0:00:01,000'+separator+
                 '2\n0:00:01,000 --> 0:00:02,000\n정상')
            cues,notes=parse_srt(raw.encode(),2,report=True)
            self.assertEqual(cues,[{'start':1.,'end':2.,'text':'정상'}])
            self.assertEqual(notes['empty'],1)
        for control in ('\v','\x1c'):
            raw=control+'1\n0:00:00,000 --> 0:00:01,000\n정상'+control
            with self.assertRaisesRegex(MediaError,'invalid_subtitles'):parse_srt(raw.encode(),2)

    def test_common_variations_report_each_adjustment(self):
        data=('4\n0:00:03,000 --> 0:00:09,000 X1:100 X2:200 Y1:0 Y2:20\n마지막\n\n'
              '2\n0:00:01,000 --> 0:00:02,000\n첫 번째\n\n'
              '3\n0:00:02,000 --> 0:00:02,500\n\n'
              '5\n0:00:08,000 --> 0:00:09,000\n범위 밖').encode('cp949')
        cues,notes=parse_srt(data,4,report=True)
        self.assertEqual(cues,[{'start':1.,'end':2.,'text':'첫 번째'}, {'start':3.,'end':4.,'text':'마지막'}])
        self.assertEqual(notes,dict(empty=1,outside=1,clipped=1,settings=1,reordered=True))

    def test_skipped_blocks_do_not_bypass_strict_validation(self):
        for text in ['\x00', '&#13;', 'a'*4001]:
            raw=f'1\n0:00:10,000 --> 0:00:11,000\n{text}'
            with self.subTest(text=text[:10]), self.assertRaisesRegex(MediaError,'invalid_subtitles'):
                parse_srt(raw.encode(),1)
        for raw in [b'0:00:10,000 --> 0:00:09,000\noutside', b'0:61:00,000 --> 0:62:00,000\nno']:
            with self.assertRaisesRegex(MediaError,'invalid_subtitles'):parse_srt(raw,1)
        raw=b'0:00:10,000 --> 0:00:11,000\noutside'
        with self.assertRaisesRegex(MediaError,'subtitle_no_usable_cues'):parse_srt(raw,1)
        with patch('media_clarity.subtitles.MAX_CUES',1), self.assertRaises(MediaError):
            parse_srt(raw+b'\n\n'+raw,1)


if __name__ == '__main__':
    unittest.main()
