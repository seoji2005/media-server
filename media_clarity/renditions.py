"""Small, optional playback derivatives. Managed originals stay authoritative."""
import hashlib
import json
import math
import os
import shutil
import uuid

from .storage import CHUNK, MediaError, no_symlink, run_media, safe_io


def selected_duration(video, audio, start):
    """MP4 stream durations or Matroska's end-time DURATION tags, when present."""
    ends = []
    try:
        for stream in [video, *audio[:1]]:
            if 'duration' in stream:
                end = float(stream.get('start_time', start)) + float(stream['duration'])
            else:
                value = stream.get('tags', {}).get('DURATION', '')
                hours, minutes, seconds = value.split(':')
                end = int(hours)*3600 + int(minutes)*60 + float(seconds)
            if not math.isfinite(end) or end <= start:
                return None
            ends.append(end)
        return max(ends) - start
    except (ValueError, TypeError):
        return None


def playback_plan(video, audio, is_mp4, multiple=False):
    codec = video.get('codec_name')
    if codec == 'hevc':
        raise MediaError('unsupported_hevc', 422)
    if video.get('pix_fmt') not in {'yuv420p', 'yuvj420p'}:
        raise MediaError('unsupported_video_depth', 422)
    if codec == 'h264':
        first = audio[0].get('codec_name') if audio else None
        if first not in {None, 'aac', 'mp3'}:
            if first not in {'ac3', 'eac3', 'dts', 'flac', 'opus', 'vorbis',
                             'pcm_s16le', 'pcm_s24le', 'pcm_s32le', 'pcm_f32le'}:
                raise MediaError('unsupported_audio_codec', 422)
            return 'audio_mp4'
        return 'original' if is_mp4 and len(audio) <= 1 and not multiple else 'remux_mp4'
    if not is_mp4 and codec in {'vp8', 'vp9'} and all(a.get('codec_name') in {'opus', 'vorbis'} for a in audio):
        return 'original' if len(audio) <= 1 and not multiple else 'remux_webm'
    raise MediaError('unsupported_codec', 422)


def prepare(store, item_id, audio_index=None):
    """Publish once, after verification; failure never rolls back an imported original."""
    if not store.import_lock.acquire(blocking=False):
        raise MediaError('import_busy', 409)
    destination = None
    try:
        source = store._row(item_id)
        index = source['audio_index'] if audio_index is None else audio_index
        if type(index) is not int or not 0 <= index < 128:
            raise MediaError('invalid_audio_track', 422)
        if source['preparation'] == 'original' and index == 0 and source['audio_tracks'] is not None:
            return store.item(item_id)
        with store.db() as db:
            ready = db.execute('SELECT id FROM renditions WHERE item_id=? AND audio_index=?', (item_id,index)).fetchone()
        if ready and source['audio_tracks'] is not None:
            store.open_verified(store.playback_row(item_id,index)).close()
            with store.db() as db:
                db.execute('UPDATE items SET audio_index=? WHERE id=?', (index,item_id))
                db.execute('UPDATE files SET preparation_error=NULL WHERE id=?', (source['file_id'],))
                db.commit()
            return store.item(item_id)
        store.open_verified(source).close()
        plan = store.probe(store.file_path(source), index) if index else store.probe(store.file_path(source))
        if source['audio_tracks'] is None or source['preparation'] == 'unchecked':
            # Existing libraries are classified on explicit first use, not by
            # scanning every video during startup. No history/caption rewrites.
            with store.db() as db:
                first_plan = store.probe(store.file_path(source)) if index else plan
                db.execute('UPDATE files SET preparation=?,audio_tracks=?,preparation_error=NULL WHERE id=?', (first_plan['preparation'],json.dumps(plan['audio_tracks']),source['file_id']))
                db.commit()
            source['preparation'] = first_plan['preparation']
            if plan['preparation'] == 'original':
                return store.item(item_id)
        if ready:
            store.open_verified(store.playback_row(item_id,index)).close()
            with store.db() as db:
                db.execute('UPDATE items SET audio_index=? WHERE id=?', (index,item_id))
                db.execute('UPDATE files SET preparation_error=NULL WHERE id=?', (source['file_id'],))
                db.commit()
            return store.item(item_id)
        if index == 0 and plan['preparation'] != source['preparation']:
            raise MediaError('managed_file_changed', 409)
        # Allow copied video/container overhead plus 192 kbit/s AAC. -fs also
        # bounds output if unexpected timestamps/metadata inflate the result.
        budget = source['size'] + math.ceil(source['duration'] * 24000) + 8 * CHUNK
        store.ensure_space(budget)
        rid = uuid.uuid4().hex
        destination = store.root / 'files' / rid
        no_symlink(destination)
        try:
            destination.mkdir(mode=0o700)
        except FileExistsError:
            destination = None
            raise MediaError('destination_collision', 409) from None
        extension = 'webm' if plan['preparation'] == 'remux_webm' else 'mp4'
        target = destination / ('original.' + extension)
        audio_options = ['-c:a', 'aac', '-b:a', '192k', '-ac', '2'] if plan['preparation'] == 'audio_mp4' else ['-c:a', 'copy']
        run_media(['ffmpeg', '-v', 'error', '-nostdin', '-xerror',
                   '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,matroska,webm',
                   '-i', str(store.file_path(source)), '-map', '0:V:0', '-map', f'0:a:{index}'+('?' if not plan['audio_tracks'] else ''),
                   '-sn', '-dn', '-map_metadata', '-1', '-map_chapters', '-1',
                   '-c:v', 'copy', *audio_options, '-fs', str(budget),
                   *(['-movflags', '+faststart'] if extension == 'mp4' else []),
                   '-n', str(target)], max(120, min(7200, math.ceil(source['duration'] * 2))), 1024)
        result = store.probe(target)
        if (result['preparation'] != 'original' or result['extension'] != extension
                or (result['width'], result['height']) != (source['width'], source['height'])
                or abs(result['duration'] - (plan['selected_duration'] or source['duration'])) > .25):
            raise MediaError('rendition_validation_failed', 422)
        with target.open('r+b') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            os.fsync(stream.fileno())
        size = target.stat().st_size
        if not size or size >= budget:
            raise MediaError('rendition_validation_failed', 422)
        store.open_verified(source).close()
        with store.db() as db:
            db.execute('INSERT INTO renditions (id,item_id,input_sha,sha256,size,extension,mime,kind,duration,audio_index) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (rid, item_id, source['sha256'], digest, size, extension, result['mime'], plan['preparation'],result['duration'],index))
            db.execute('UPDATE items SET audio_index=? WHERE id=?', (index,item_id))
            db.execute('UPDATE files SET preparation_error=NULL WHERE id=?', (source['file_id'],))
            db.commit()
        destination = None  # Committed files are never part of failure cleanup.
        return store.item(item_id)
    except (MediaError, OSError) as exc:
        error = safe_io(exc) if isinstance(exc, OSError) else exc
        with store.db() as db:
            db.execute('UPDATE files SET preparation_error=? WHERE id=(SELECT file_id FROM items WHERE id=?)', (error.code, item_id))
            db.commit()
        raise error from None
    finally:
        try:
            if destination is not None:
                shutil.rmtree(destination)
        finally:
            store.import_lock.release()
