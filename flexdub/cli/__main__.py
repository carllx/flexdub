import argparse
import asyncio
import os
import tempfile
from typing import Optional

from flexdub.core.subtitle import read_srt, write_srt, apply_text_options, to_segments, from_segments, SRTItem
from flexdub.core.rebalance import rebalance_intervals
from flexdub.core.audio import concat_wavs, mux_audio_video, make_silence, media_duration_ms, detect_negative_ts
from flexdub.core.audio import extract_audio_track, write_sync_audit
from flexdub.pipelines.dubbing import build_audio_from_srt
from flexdub.core.lang import detect_language, recommended_voice


def _parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("merge")
    m.add_argument("srt_path")
    m.add_argument("video_path")
    m.add_argument("-o", "--output", default=None)
    m.add_argument("--backend", choices=["edge_tts", "doubao"], required=True)
    m.add_argument("--voice", default="zh-CN-YunjianNeural")
    m.add_argument("--ar", type=int, default=48000)
    m.add_argument("--keep-brackets", action="store_true")
    m.add_argument("--strip-meta", action="store_true")
    m.add_argument("--strip-noise", action="store_true")
    m.add_argument("--target-cpm", type=int, default=180)
    m.add_argument("--panic-cpm", type=int, default=300)
    m.add_argument("--max-shift", type=int, default=1000)
    m.add_argument("--no-rebalance", action="store_true")
    m.add_argument("--jobs", type=int, default=4)
    m.add_argument("--no-progress", action="store_true")
    m.add_argument("--subtitle-path", default=None)
    m.add_argument("--subtitle-lang", default="zh")
    m.add_argument("--debug-sync", action="store_true")
    m.add_argument("--robust-ts", action="store_true")
    m.add_argument("--clustered", action="store_true")
    m.add_argument("--smart-split", action="store_true")
    m.add_argument("--auto-dual-srt", action="store_true")
    m.add_argument("--llm-dual-srt", action="store_true")
    m.add_argument("--no-fallback", action="store_true")
    m.add_argument("--voice-map", default=None)
    m.add_argument("--mode", choices=["elastic-audio", "elastic-video"], default="elastic-video", help="Pipeline mode: elastic-audio (compress audio to fit video) or elastic-video (stretch video to fit audio, default)")
    m.add_argument("--skip-length-check", action="store_true", help="Skip character length validation for TTS (default threshold: 75 chars)")

    r = sub.add_parser("rebalance")
    r.add_argument("srt_path")
    r.add_argument("-o", "--output", default=None)
    r.add_argument("--target-cpm", type=int, default=180)
    r.add_argument("--panic-cpm", type=int, default=300)
    r.add_argument("--max-shift", type=int, default=1000)
    r.add_argument("--keep-brackets", action="store_true")
    r.add_argument("--strip-meta", action="store_true")
    r.add_argument("--strip-noise", action="store_true")

    a = sub.add_parser("audit")
    a.add_argument("srt_path")
    a.add_argument("--min-cpm", type=int, default=180)
    a.add_argument("--max-cpm", type=int, default=220)
    a.add_argument("--keep-brackets", action="store_true")
    a.add_argument("--strip-meta", action="store_true")
    a.add_argument("--save", default=None)
    a.add_argument("--strip-noise", action="store_true")

    jm = sub.add_parser("json_merge")
    jm.add_argument("segments_json")
    jm.add_argument("video_path")
    jm.add_argument("-o", "--output", default=None)
    jm.add_argument("--source", choices=["auto", "whisperx", "gemini"], default="auto")
    jm.add_argument("--backend", choices=["edge_tts", "doubao"], required=True)
    jm.add_argument("--voice", default="zh-CN-YunjianNeural")
    jm.add_argument("--ar", type=int, default=48000)
    jm.add_argument("--keep-brackets", action="store_true")
    jm.add_argument("--strip-meta", action="store_true")
    jm.add_argument("--strip-noise", action="store_true")
    jm.add_argument("--target-cpm", type=int, default=180)
    jm.add_argument("--panic-cpm", type=int, default=300)
    jm.add_argument("--max-shift", type=int, default=1000)
    jm.add_argument("--no-rebalance", action="store_true")
    jm.add_argument("--jobs", type=int, default=4)
    jm.add_argument("--no-progress", action="store_true")
    jm.add_argument("--subtitle-path", default=None)
    jm.add_argument("--subtitle-lang", default="zh")
    jm.add_argument("--debug-sync", action="store_true")
    jm.add_argument("--robust-ts", action="store_true")
    jm.add_argument("--clustered", action="store_true")
    jm.add_argument("--smart-split", action="store_true")
    jm.add_argument("--no-fallback", action="store_true")
    jm.add_argument("--voice-map", default=None)

    ja = sub.add_parser("json_audit")
    ja.add_argument("segments_json")
    ja.add_argument("--source", choices=["auto", "whisperx", "gemini"], default="auto")
    ja.add_argument("--min-cpm", type=int, default=180)
    ja.add_argument("--max-cpm", type=int, default=220)
    ja.add_argument("--save", default=None)
    vp = sub.add_parser("validate_project")
    vp.add_argument("project_dir")
    pm = sub.add_parser("project_merge")
    pm.add_argument("project_dir")
    pm.add_argument("-o", "--output_dir", default=None)
    pm.add_argument("--backend", choices=["edge_tts", "doubao"], required=True)
    pm.add_argument("--voice", default=None)
    pm.add_argument("--ar", type=int, default=48000)
    pm.add_argument("--keep-brackets", action="store_true")
    pm.add_argument("--strip-meta", action="store_true")
    pm.add_argument("--strip-noise", action="store_true")
    pm.add_argument("--target-cpm", type=int, default=180)
    pm.add_argument("--panic-cpm", type=int, default=300)
    pm.add_argument("--max-shift", type=int, default=1000)
    pm.add_argument("--no-rebalance", action="store_true")
    pm.add_argument("--jobs", type=int, default=4)
    pm.add_argument("--no-progress", action="store_true")
    pm.add_argument("--embed-subtitle", choices=["none", "original", "rebalance", "display"], default="rebalance")
    pm.add_argument("--subtitle-lang", default="en")
    pm.add_argument("--target-lang", default=None)
    pm.add_argument("--auto-voice", action="store_true")
    pm.add_argument("--debug-sync", action="store_true")
    pm.add_argument("--robust-ts", action="store_true")
    pm.add_argument("--clustered", action="store_true")
    pm.add_argument("--smart-split", action="store_true")
    pm.add_argument("--auto-dual-srt", action="store_true")
    pm.add_argument("--llm-dual-srt", action="store_true")
    pm.add_argument("--no-fallback", action="store_true")
    pm.add_argument("--voice-map", default=None)
    sa = sub.add_parser("sync_audit")
    sa.add_argument("video_path")
    sa.add_argument("srt_path")
    sa.add_argument("-o", "--output_dir", default=None)
    sa.add_argument("--ar", type=int, default=48000)
    sa.add_argument("--win-ms", type=int, default=20)
    rw = sub.add_parser("rewrite")
    rw.add_argument("srt_path")
    rw.add_argument("-o", "--output", default=None)
    rw.add_argument("--keep-brackets", action="store_true")
    rw.add_argument("--strip-meta", action="store_true")
    rw.add_argument("--strip-noise", action="store_true")
    rw.add_argument("--max-chars", type=int, default=250)
    rw.add_argument("--max-duration", type=int, default=15000)
    fl = sub.add_parser("fluency")
    fl.add_argument("srt_path")
    fl.add_argument("--save", default=None)
    
    # QA command for Mode B quality checks
    qa = sub.add_parser("qa")
    qa.add_argument("srt_path")
    qa.add_argument("--voice-map", default=None)
    qa.add_argument("--video-duration-ms", type=int, default=None)
    qa.add_argument("--max-chars", type=int, default=250)
    qa.add_argument("--max-duration-ms", type=int, default=15000)
    qa.add_argument("--tts-char-threshold", type=int, default=75, help="Character threshold for TTS stability (default: 75)")
    qa.add_argument("--backend", choices=["edge_tts", "doubao"], default="doubao", help="TTS backend for threshold check")
    qa.add_argument("-o", "--output", default=None, help="Output QA report to file")
    
    # gs_align command: align gs.md with SRT timeline
    ga = sub.add_parser("gs_align", help="Align gs.md (human-edited transcript) with SRT timeline")
    ga.add_argument("gs_path", help="Path to gs.md file")
    ga.add_argument("srt_path", help="Path to original SRT file (for timeline)")
    ga.add_argument("-o", "--output", default=None, help="Output audio.srt path")
    ga.add_argument("--voice-map-output", default=None, help="Output voice_map.json path")
    ga.add_argument("--max-chars", type=int, default=75, help="Max characters per segment (default: 75 for Doubao TTS)")
    ga.add_argument("--max-duration-ms", type=int, default=15000, help="Max duration per segment in ms")
    ga.add_argument("--target-cpm", type=int, default=180, help="Target CPM for rebalancing")
    ga.add_argument("--fuzzy-window-ms", type=int, default=2000, help="Fuzzy matching window for anchor points (ms)")
    ga.add_argument("--extract-glossary", action="store_true", help="Extract glossary from gs.md")
    ga.add_argument("--glossary-output", default=None, help="Output glossary.yaml path")
    
    # semantic_refine command: refine SRT translation using gs.md as semantic context
    sr = sub.add_parser("semantic_refine", help="Refine SRT translation using gs.md as semantic context")
    sr.add_argument("gs_path", help="Path to gs.md file (semantic context)")
    sr.add_argument("srt_path", help="Path to SRT file to refine")
    sr.add_argument("-o", "--output", default=None, help="Output refined.audio.srt path")
    sr.add_argument("--include-speaker-tags", action="store_true", help="Include speaker tags in output")
    sr.add_argument("--checkpoint-dir", default=None, help="Directory for checkpoint files (resume support)")
    sr.add_argument("--api-key", default=None, help="LLM API key (or set FLEXDUB_LLM_API_KEY env)")
    sr.add_argument("--base-url", default=None, help="LLM API base URL (or set FLEXDUB_LLM_BASE_URL env)")
    sr.add_argument("--model", default=None, help="LLM model name (or set FLEXDUB_LLM_MODEL env)")
    
    return p.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = _parse_args(argv)
    if args.cmd == "merge":
        items = read_srt(args.srt_path)
        orig_texts = [i.text for i in items]
        items = [SRTItem(i.start_ms, i.end_ms, i.text) for i in items]
        if not args.no_rebalance and not args.clustered:
            segs = to_segments(items)
            segs = rebalance_intervals(segs, target_cpm=args.target_cpm, max_shift_ms=args.max_shift, panic_cpm=args.panic_cpm)
            items = from_segments(segs)
            after_texts = [i.text for i in items]
            if after_texts != orig_texts:
                raise RuntimeError("text mutated in script stage")
        display_srt = None
        audio_srt = None
        if args.auto_dual_srt:
            base, _ = os.path.splitext(os.path.basename(args.video_path))
            out_dir = os.path.dirname(args.video_path)
            os.makedirs(out_dir, exist_ok=True)
            display_srt = os.path.join(out_dir, base + ".display.srt")
            audio_srt = os.path.join(out_dir, base + ".audio.srt")
            if args.llm_dual_srt:
                from flexdub.core.subtitle import llm_generate_dual_srt as _llm_dual
                d_items, a_items = _llm_dual(items)
                write_srt(display_srt, d_items)
                write_srt(audio_srt, a_items)
            else:
                from flexdub.core.subtitle import semantic_restructure as _semantic_restructure
                write_srt(display_srt, items)
                write_srt(audio_srt, _semantic_restructure(items))
        backend = args.backend
        voice = args.voice
        ar = args.ar
        jobs = args.jobs
        if args.no_fallback:
            jobs = 1
        
        # Mode selection: elastic-audio (A) or elastic-video (B)
        mode = getattr(args, 'mode', 'elastic-audio')
        video_segments = []  # Initialize for mode B
        
        if mode == "elastic-video":
            # Mode B: Elastic Video Pipeline
            from flexdub.pipelines.elastic_video import build_elastic_video_from_srt
            vmap = None
            if args.voice_map:
                try:
                    import json as _json
                    with open(args.voice_map, "r", encoding="utf-8") as vf:
                        vmap = _json.load(vf)
                except Exception:
                    vmap = None
            
            try:
                wavs, new_items, video_segments, sync_diagnostics = asyncio.run(
                    build_elastic_video_from_srt(
                        items, args.video_path, voice, backend, ar,
                        jobs=jobs, progress=not args.no_progress, voice_map=vmap,
                        debug_sync=args.debug_sync,
                        skip_length_check=args.skip_length_check
                    )
                )
                # Update items with new timeline
                items = new_items
            except Exception as e:
                print(f"[ERROR] elastic-video mode failed: {e}")
                if args.no_fallback:
                    return 1
                raise
        else:
            # Mode A: Elastic Audio Pipeline (original)
            use_clustered = args.clustered or args.auto_dual_srt
            if use_clustered:
                from flexdub.pipelines.dubbing import build_audio_from_srt_clustered as _build
            else:
                from flexdub.pipelines.dubbing import build_audio_from_srt as _build
            try:
                if use_clustered:
                    vmap = None
                    if args.voice_map:
                        try:
                            import json as _json
                            with open(args.voice_map, "r", encoding="utf-8") as vf:
                                vmap = _json.load(vf)
                        except Exception:
                            vmap = None
                    wavs = asyncio.run(_build(items, voice, backend, ar, jobs=jobs, progress=not args.no_progress, smart_split=args.smart_split, voice_map=vmap))
                else:
                    wavs = asyncio.run(_build(items, voice, backend, ar, jobs=jobs, progress=not args.no_progress))
            except Exception as e:
                print(f"[ERROR] TTS synthesis failed: {e}")
                return 1
        out = args.output
        if out is None:
            base, _ = os.path.splitext(os.path.basename(args.video_path))
            out = os.path.join(os.path.dirname(args.video_path), base + ".dub.mp4")
        
        if mode == "elastic-video":
            # Mode B: Concatenate video segments and merge with audio
            from flexdub.pipelines.elastic_video import concatenate_video_segments, generate_mode_b_subtitle
            from flexdub.core.subtitle import detect_gaps
            
            tmp_video = tempfile.mktemp(suffix=".mp4")
            concatenate_video_segments(video_segments, tmp_video)
            
            # Concatenate audio segments
            tmp_mix = tempfile.mktemp(suffix=".wav")
            concat_wavs(wavs, tmp_mix)
            
            # Generate Mode B subtitle file (*.mode_b.srt)
            base_name = os.path.splitext(os.path.basename(args.srt_path))[0]
            mode_b_srt_path = os.path.join(os.path.dirname(out), base_name + ".mode_b.srt")
            
            # Get TTS durations from the new items (items already has new timeline)
            tts_durations_for_srt = [it.end_ms - it.start_ms for it in items]
            
            # Detect gaps from original items for subtitle generation
            orig_items = read_srt(args.srt_path)
            gaps_for_srt = detect_gaps(orig_items, min_gap_ms=100)
            
            generate_mode_b_subtitle(
                orig_items, tts_durations_for_srt, gaps_for_srt, mode_b_srt_path,
                keep_speaker_tags=True
            )
            print(f"[MODE_B] Generated subtitle: {mode_b_srt_path}")
            
            # Write updated subtitle with new timeline
            if args.auto_dual_srt and display_srt:
                write_srt(display_srt, items)
            
            # Write sync diagnostics if enabled
            if args.debug_sync and sync_diagnostics:
                diag_path = os.path.join(os.path.dirname(out), os.path.splitext(os.path.basename(out))[0] + ".sync_diag.log")
                with open(diag_path, "w", encoding="utf-8") as df:
                    df.write(f"[MODE_B_SYNC_DIAGNOSTICS]\n")
                    df.write(f"total_original_ms={sync_diagnostics.total_original_ms}\n")
                    df.write(f"total_new_ms={sync_diagnostics.total_new_ms}\n")
                    df.write(f"overall_ratio={sync_diagnostics.overall_ratio:.4f}\n")
                    df.write(f"\n[SEGMENTS]\n")
                    for seg in sync_diagnostics.segments:
                        seg_type = "GAP" if seg.is_gap else ("BLANK" if seg.is_blank else "NORMAL")
                        df.write(f"idx={seg.index} type={seg_type} orig={seg.original_duration_ms}ms tts={seg.tts_duration_ms}ms ratio={seg.stretch_ratio:.3f} new_start={seg.new_start_ms}ms new_end={seg.new_end_ms}ms text={seg.text}\n")
                    if sync_diagnostics.warnings:
                        df.write(f"\n[WARNINGS]\n")
                        for w in sync_diagnostics.warnings:
                            df.write(f"{w}\n")
                print(f"[MODE_B] Sync diagnostics written to: {diag_path}")
            
            # Verify total duration consistency
            expected_duration_ms = sum(it.end_ms - it.start_ms for it in items)
            # Add gap durations
            for g in gaps_for_srt:
                expected_duration_ms += g.duration_ms
            
            # Get actual audio duration
            actual_audio_duration_ms = media_duration_ms(tmp_mix)
            duration_diff_ms = abs(expected_duration_ms - actual_audio_duration_ms)
            
            print(f"[MODE_B] Duration verification:")
            print(f"[MODE_B]   Expected (TTS + gaps): {expected_duration_ms}ms")
            print(f"[MODE_B]   Actual audio: {actual_audio_duration_ms}ms")
            print(f"[MODE_B]   Difference: {duration_diff_ms}ms")
            
            if duration_diff_ms > 100:  # More than 100ms difference
                print(f"[MODE_B] WARNING: Duration mismatch exceeds 100ms!")
            
            # Merge stretched video with natural-speed audio
            auto_robust = detect_negative_ts(tmp_video)
            sub_path = args.subtitle_path
            # For Mode B, default to using the generated mode_b.srt
            if sub_path is None:
                sub_path = mode_b_srt_path
            elif args.auto_dual_srt and display_srt is not None:
                sub_path = display_srt
            mux_audio_video(tmp_video, tmp_mix, out, subtitle_path=sub_path, subtitle_lang=args.subtitle_lang, robust_ts=(args.robust_ts or auto_robust))
        else:
            # Mode A: Original elastic-audio pipeline
            ordered: list[str] = []
            dbg_lines: list[str] = []
            if items:
                v_ms = media_duration_ms(args.video_path)
                pre_ms = max(0, items[0].start_ms)
                if pre_ms > 0:
                    pre = tempfile.mktemp(suffix=".wav")
                    make_silence(pre, pre_ms, sr=ar)
                    ordered.append(pre)
                dbg_lines.append(f"[VIDEO] duration_ms={v_ms}")
                dbg_lines.append(f"[PRE] ms={pre_ms}")
                sample_idx = list(range(0, min(len(items), 20)))
                for si in sample_idx:
                    dbg_lines.append(f"[QA] idx={si} same_text={orig_texts[si] == items[si].text}")
                for i, w in enumerate(wavs):
                    ordered.append(w)
                    if i + 1 < len(items):
                        gap = items[i + 1].start_ms - items[i].end_ms
                        if gap > 0:
                            g = tempfile.mktemp(suffix=".wav")
                            make_silence(g, gap, sr=ar)
                            ordered.append(g)
                        dbg_lines.append(f"[SEG] idx={i} start={items[i].start_ms} end={items[i].end_ms} gap_to_next={gap}")
                last_end = items[-1].end_ms
                tail = max(0, v_ms - last_end)
                if tail > 0:
                    t = tempfile.mktemp(suffix=".wav")
                    make_silence(t, tail, sr=ar)
                    ordered.append(t)
                dbg_lines.append(f"[TAIL] ms={tail}")
            tmp_mix = tempfile.mktemp(suffix=".wav")
            concat_wavs(ordered or wavs, tmp_mix)
            if args.debug_sync:
                dbg_path = os.path.join(os.path.dirname(out), os.path.splitext(os.path.basename(out))[0] + ".sync_debug.log")
                with open(dbg_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(dbg_lines))
                print(dbg_path)
            sub_path = args.subtitle_path
            if sub_path is None and args.auto_dual_srt and display_srt is not None:
                sub_path = display_srt
            auto_robust = detect_negative_ts(args.video_path)
            mux_audio_video(args.video_path, tmp_mix, out, subtitle_path=sub_path, subtitle_lang=args.subtitle_lang, robust_ts=(args.robust_ts or auto_robust))
        return 0
    if args.cmd == "json_merge":
        from flexdub.core.io import read_segments_json
        segs = read_segments_json(args.segments_json, source=args.source)
        items = from_segments(segs)
        orig_texts = [i.text for i in items]
        items = [SRTItem(i.start_ms, i.end_ms, i.text) for i in items]
        if not args.no_rebalance and not args.clustered:
            segs2 = rebalance_intervals([type("S", (), {"start_ms": i.start_ms, "end_ms": i.end_ms, "text": i.text}) for i in items], target_cpm=args.target_cpm, max_shift_ms=args.max_shift, panic_cpm=args.panic_cpm)
            items = from_segments(segs2)
            after_texts = [i.text for i in items]
            if after_texts != orig_texts:
                raise RuntimeError("text mutated in script stage")
        backend = args.backend
        voice = args.voice
        ar = args.ar
        jobs = args.jobs
        if args.no_fallback:
            jobs = 1
        if args.clustered:
            from flexdub.pipelines.dubbing import build_audio_from_srt_clustered as _build2
        else:
            from flexdub.pipelines.dubbing import build_audio_from_srt as _build2
        try:
            if args.clustered:
                vmap2 = None
                if args.voice_map:
                    try:
                        import json as _json
                        with open(args.voice_map, "r", encoding="utf-8") as vf2:
                            vmap2 = _json.load(vf2)
                    except Exception:
                        vmap2 = None
                wavs = asyncio.run(_build2(items, voice, backend, ar, jobs=jobs, progress=not args.no_progress, smart_split=args.smart_split, voice_map=vmap2))
            else:
                wavs = asyncio.run(_build2(items, voice, backend, ar, jobs=jobs, progress=not args.no_progress))
        except Exception as e:
            print(f"[ERROR] TTS synthesis failed: {e}")
            return 1
        ordered2: list[str] = []
        dbg_lines2: list[str] = []
        if items:
            v_ms2 = media_duration_ms(args.video_path)
            pre_ms2 = max(0, items[0].start_ms)
            if pre_ms2 > 0:
                pre2 = tempfile.mktemp(suffix=".wav")
                make_silence(pre2, pre_ms2, sr=ar)
                ordered2.append(pre2)
            dbg_lines2.append(f"[VIDEO] duration_ms={v_ms2}")
            dbg_lines2.append(f"[PRE] ms={pre_ms2}")
            sample_idx2 = list(range(0, min(len(items), 20)))
            for si in sample_idx2:
                dbg_lines2.append(f"[QA] idx={si} same_text={orig_texts[si] == items[si].text}")
            for i, w in enumerate(wavs):
                ordered2.append(w)
                if i + 1 < len(items):
                    gap2 = items[i + 1].start_ms - items[i].end_ms
                    if gap2 > 0:
                        g2 = tempfile.mktemp(suffix=".wav")
                        make_silence(g2, gap2, sr=ar)
                        ordered2.append(g2)
                    dbg_lines2.append(f"[SEG] idx={i} start={items[i].start_ms} end={items[i].end_ms} gap_to_next={gap2}")
            last_end2 = items[-1].end_ms
            tail2 = max(0, v_ms2 - last_end2)
            if tail2 > 0:
                t2 = tempfile.mktemp(suffix=".wav")
                make_silence(t2, tail2, sr=ar)
                ordered2.append(t2)
            dbg_lines2.append(f"[TAIL] ms={tail2}")
        tmp_mix = tempfile.mktemp(suffix=".wav")
        concat_wavs(ordered2 or wavs, tmp_mix)
        out = args.output
        if out is None:
            base, _ = os.path.splitext(os.path.basename(args.video_path))
            out = os.path.join(os.path.dirname(args.video_path), base + ".dub.mp4")
        if args.debug_sync:
            dbg_path2 = os.path.join(os.path.dirname(out), os.path.splitext(os.path.basename(out))[0] + ".sync_debug.log")
            with open(dbg_path2, "w", encoding="utf-8") as f:
                f.write("\n".join(dbg_lines2))
            print(dbg_path2)
        auto_robust2 = detect_negative_ts(args.video_path)
        mux_audio_video(args.video_path, tmp_mix, out, subtitle_path=args.subtitle_path, subtitle_lang=args.subtitle_lang, robust_ts=(args.robust_ts or auto_robust2))
        return 0
    if args.cmd == "rebalance":
        items = read_srt(args.srt_path)
        orig_texts = [i.text for i in items]
        items = [SRTItem(i.start_ms, i.end_ms, i.text) for i in items]
        segs = to_segments(items)
        segs = rebalance_intervals(segs, target_cpm=args.target_cpm, max_shift_ms=args.max_shift, panic_cpm=args.panic_cpm)
        items2 = from_segments(segs)
        after_texts = [i.text for i in items2]
        if after_texts != orig_texts:
            raise RuntimeError("text mutated in script stage")
        out = args.output
        if out is None:
            base = os.path.basename(args.srt_path)
            name, ext = os.path.splitext(base)
            out = os.path.join(os.path.dirname(args.srt_path), name + ".rebalance.srt")
        write_srt(out, items2)
        print(out)
        return 0
    if args.cmd == "audit":
        items = read_srt(args.srt_path)
        items = [SRTItem(i.start_ms, i.end_ms, i.text) for i in items]
        import csv
        def cpm_of(it):
            dur = max(1, it.end_ms - it.start_ms)
            chars = len(it.text.strip())
            return chars / (dur / 60000.0)
        rows = []
        for idx, it in enumerate(items, start=1):
            cpm = cpm_of(it)
            rows.append((idx, cpm, it.end_ms - it.start_ms, len(it.text.strip()), it.start_ms, it.end_ms))
        bad = [r for r in rows if r[1] < args.min_cpm or r[1] > args.max_cpm]
        for r in bad:
            print(f"{r[0]}\t{r[1]:.1f}\t{r[2]}\t{r[3]}\t{r[4]}\t{r[5]}")
        if args.save:
            with open(args.save, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["index", "cpm", "duration_ms", "chars", "start_ms", "end_ms"])
                for r in rows:
                    w.writerow(list(r))
            print(args.save)
        return 0
    if args.cmd == "json_audit":
        from flexdub.core.io import read_segments_json, audit_rows_from_segments
        segs = read_segments_json(args.segments_json, source=args.source)
        rows = audit_rows_from_segments(segs)
        bad = [r for r in rows if r[1] < args.min_cpm or r[1] > args.max_cpm]
        for r in bad:
            print(f"{r[0]}\t{r[1]:.1f}\t{r[2]}\t{r[3]}\t{r[4]}\t{r[5]}")
        if args.save:
            import csv
            with open(args.save, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["index", "cpm", "duration_ms", "chars", "start_ms", "end_ms"])
                for r in rows:
                    w.writerow(list(r))
            print(args.save)
        return 0
    if args.cmd == "validate_project":
        import glob
        pdir = os.path.abspath(args.project_dir)
        mp4s = glob.glob(os.path.join(pdir, "*.mp4"))
        srts = glob.glob(os.path.join(pdir, "*.srt"))
        ok = True
        if len(mp4s) == 0:
            print("ERROR: no MP4 found")
            ok = False
        if len(srts) == 0:
            print("ERROR: no SRT found")
            ok = False
        if len(mp4s) > 1:
            print("WARN: multiple MP4s, using the first")
        if len(srts) > 1:
            print("WARN: multiple SRTs, using the first")
        if ok:
            print("OK")
            print(mp4s[0])
            print(srts[0])
            base = os.path.basename(pdir)
            out_dir = os.path.join(os.path.dirname(os.path.dirname(pdir)), "output", base)
            os.makedirs(out_dir, exist_ok=True)
            vjson = os.path.join(out_dir, "validation.json")
            lang = "unknown"
            rec_voice = None
            auto_robust_hint = False
            try:
                items = read_srt(srts[0])
                lang = detect_language([i.text for i in items])
                rec_voice = recommended_voice(lang)
            except Exception:
                rec_voice = "zh-CN-YunjianNeural"
            try:
                auto_robust_hint = detect_negative_ts(mp4s[0])
            except Exception:
                auto_robust_hint = False
            import json
            with open(vjson, "w", encoding="utf-8") as f:
                json.dump({
                    "project": base,
                    "mp4": mp4s[0],
                    "srt": srts[0],
                    "lang": lang,
                    "recommended_voice": rec_voice,
                    "recommend_robust_ts": auto_robust_hint,
                }, f, ensure_ascii=False, indent=2)
            print(f"LANG={lang}")
            if rec_voice:
                print(f"RECOMMENDED_VOICE={rec_voice}")
            if auto_robust_hint:
                print("RECOMMEND_ROBUST_TS=true")
            print(vjson)
            return 0
        return 1
    if args.cmd == "project_merge":
        import glob
        import json
        pdir = os.path.abspath(args.project_dir)
        mp4s = glob.glob(os.path.join(pdir, "*.mp4"))
        srts = glob.glob(os.path.join(pdir, "*.srt"))
        def _issue(path: str, title: str, detail: str) -> None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# Issue: {title}\n\n")
                f.write("## Detail\n\n")
                f.write(detail + "\n")
                f.write("\n## Fix Template\n\n")
                f.write("- Root cause:\n- Impact:\n- Fix steps:\n- Verification:\n")
        try:
            if not mp4s or not srts:
                raise RuntimeError("project structure invalid: require one MP4 and one SRT")
            video_path = mp4s[0]
            srt_path = srts[0]
            base = os.path.basename(pdir)
            out_dir = args.output_dir or os.path.join(os.path.dirname(os.path.dirname(pdir)), "output", base)
            os.makedirs(out_dir, exist_ok=True)
            log_path = os.path.join(out_dir, "process.log")
            report_path = os.path.join(out_dir, "report.json")
            cpm_csv = os.path.join(out_dir, "cpm.csv")
            rebalance_srt = os.path.join(out_dir, os.path.splitext(os.path.basename(srt_path))[0] + ".rebalance.srt")
            display_srt = os.path.join(out_dir, os.path.splitext(os.path.basename(srt_path))[0] + ".display.srt")
            audio_srt = os.path.join(out_dir, os.path.splitext(os.path.basename(srt_path))[0] + ".audio.srt")
            with open(log_path, "w", encoding="utf-8") as log:
                log.write("[START] project_merge\n")
                items = read_srt(srt_path)
                orig_texts = [i.text for i in items]
                items = [SRTItem(i.start_ms, i.end_ms, i.text) for i in items]
                if args.auto_dual_srt:
                    if args.llm_dual_srt:
                        from flexdub.core.subtitle import llm_generate_dual_srt as _llm_dual
                        d_items, a_items = _llm_dual(items)
                        write_srt(display_srt, d_items)
                        write_srt(audio_srt, a_items)
                    else:
                        from flexdub.core.subtitle import semantic_restructure as _semantic_restructure
                        write_srt(display_srt, items)
                        write_srt(audio_srt, _semantic_restructure(items))
                    log.write("[DUAL] display.srt & audio.srt written\n")
                rows = []
                for idx, it in enumerate(items, start=1):
                    dur = max(1, it.end_ms - it.start_ms)
                    chars = len(it.text.strip())
                    cpm = chars / (dur / 60000.0)
                    rows.append((idx, cpm, dur, chars, it.start_ms, it.end_ms))
                with open(cpm_csv, "w", newline="", encoding="utf-8") as f:
                    import csv
                    w = csv.writer(f)
                    w.writerow(["index", "cpm", "duration_ms", "chars", "start_ms", "end_ms"])
                    for r in rows:
                        w.writerow(list(r))
                log.write("[AUDIT] cpm.csv written\n")
                if not args.no_rebalance and not args.clustered:
                    segs = [type("S", (), {"start_ms": i.start_ms, "end_ms": i.end_ms, "text": i.text}) for i in items]
                    segs2 = rebalance_intervals(segs, target_cpm=args.target_cpm, max_shift_ms=args.max_shift, panic_cpm=args.panic_cpm)
                    items = [SRTItem(i.start_ms, i.end_ms, i.text) for i in segs2]
                    after_texts = [i.text for i in items]
                    if after_texts != orig_texts:
                        raise RuntimeError("text mutated in script stage")
                    write_srt(rebalance_srt, items)
                    log.write("[REBALANCE] rebalance.srt written\n")
                tl = args.target_lang
                if tl is None:
                    tl = detect_language([i.text for i in items])
                backend = args.backend
                voice = args.voice if args.voice is not None else (recommended_voice(tl) if args.auto_voice else None)
                if voice is None:
                    voice = recommended_voice(tl)
                log.write(f"[LANG] {tl}\n")
                log.write(f"[VOICE] {voice}\n")
                ar = args.ar
                jobs = args.jobs
                if args.no_fallback:
                    jobs = 1
                try:
                    use_clustered = args.clustered or args.auto_dual_srt
                    if use_clustered:
                        from flexdub.pipelines.dubbing import build_audio_from_srt_clustered as _build3
                        vmap3 = None
                        vmap_path = args.voice_map or os.path.join(pdir, "voice_map.json")
                        if os.path.exists(vmap_path):
                            try:
                                with open(vmap_path, "r", encoding="utf-8") as vf3:
                                    vmap3 = json.load(vf3)
                            except Exception:
                                vmap3 = None
                        wavs = asyncio.run(_build3(items, voice, backend, ar, jobs=jobs, progress=not args.no_progress, smart_split=args.smart_split, voice_map=vmap3))
                    else:
                        from flexdub.pipelines.dubbing import build_audio_from_srt as _build3
                        wavs = asyncio.run(_build3(items, voice, backend, ar, jobs=jobs, progress=not args.no_progress))
                except Exception as e:
                    log.write(f"[ERROR] synth failed: {e}\n")
                    raise e
                ordered: list[str] = []
                dbg_lines3: list[str] = []
                if items:
                    v_ms = media_duration_ms(video_path)
                    pre_ms = max(0, items[0].start_ms)
                    if pre_ms > 0:
                        pre = tempfile.mktemp(suffix=".wav")
                        make_silence(pre, pre_ms, sr=ar)
                        ordered.append(pre)
                    dbg_lines3.append(f"[VIDEO] duration_ms={v_ms}")
                    dbg_lines3.append(f"[PRE] ms={pre_ms}")
                    sample_idx3 = list(range(0, min(len(items), 20)))
                    for si in sample_idx3:
                        dbg_lines3.append(f"[QA] idx={si} same_text={orig_texts[si] == items[si].text}")
                    for i, w in enumerate(wavs):
                        ordered.append(w)
                        if i + 1 < len(items):
                            gap = items[i + 1].start_ms - items[i].end_ms
                            if gap > 0:
                                g = tempfile.mktemp(suffix=".wav")
                                make_silence(g, gap, sr=ar)
                                ordered.append(g)
                            dbg_lines3.append(f"[SEG] idx={i} start={items[i].start_ms} end={items[i].end_ms} gap_to_next={gap}")
                    last_end = items[-1].end_ms
                    tail = max(0, v_ms - last_end)
                    if tail > 0:
                        t = tempfile.mktemp(suffix=".wav")
                        make_silence(t, tail, sr=ar)
                        ordered.append(t)
                    dbg_lines3.append(f"[TAIL] ms={tail}")
                tmp_mix = tempfile.mktemp(suffix=".wav")
                concat_wavs(ordered or wavs, tmp_mix)
                out_mp4 = os.path.join(out_dir, base + ".dub.mp4")
                subtitle_path = None
                embed_choice = args.embed_subtitle
                if args.auto_dual_srt and embed_choice == "rebalance":
                    embed_choice = "display"
                if embed_choice == "original":
                    subtitle_path = srt_path
                elif embed_choice == "rebalance" and not args.no_rebalance:
                    subtitle_path = rebalance_srt
                elif embed_choice == "display" and args.auto_dual_srt:
                    subtitle_path = display_srt
                if args.debug_sync:
                    dbg_path3 = os.path.join(out_dir, base + ".sync_debug.log")
                    with open(dbg_path3, "w", encoding="utf-8") as f:
                        f.write("\n".join(dbg_lines3))
                    print(dbg_path3)
                auto_robust3 = detect_negative_ts(video_path)
                mux_audio_video(video_path, tmp_mix, out_mp4, subtitle_path=subtitle_path, subtitle_lang=args.subtitle_lang, robust_ts=(args.robust_ts or auto_robust3))
                log.write("[MERGE] output mp4 written\n")
                report = {
                    "project": base,
                    "input_video": video_path,
                    "input_srt": srt_path,
                    "output_mp4": out_mp4,
                    "rebalance_srt": rebalance_srt if not args.no_rebalance else None,
                    "display_srt": display_srt if args.auto_dual_srt else None,
                    "audio_srt": audio_srt if args.auto_dual_srt else None,
                    "cpm_csv": cpm_csv,
                }
                # merge validation.json if present
                vjson = os.path.join(out_dir, "validation.json")
                try:
                    if os.path.exists(vjson):
                        with open(vjson, "r", encoding="utf-8") as vf:
                            vdata = json.load(vf)
                        report.update({
                            "lang": vdata.get("lang"),
                            "recommended_voice": vdata.get("recommended_voice"),
                            "validated": True,
                        })
                except Exception:
                    report["validated"] = False
                with open(report_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                log.write("[DONE] report.json written\n")
            print(report_path)
            return 0
        except Exception as e:
            base = os.path.basename(os.path.abspath(args.project_dir))
            out_dir = args.output_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(args.project_dir))), "output", base)
            os.makedirs(out_dir, exist_ok=True)
            issue_dir = os.path.join(out_dir, "issues")
            os.makedirs(issue_dir, exist_ok=True)
            issue_path = os.path.join(issue_dir, "issue.md")
            _issue(issue_path, "project_merge failure", str(e))
            print(issue_path)
            return 1
    if args.cmd == "sync_audit":
        base = os.path.splitext(os.path.basename(args.video_path))[0]
        out_dir = args.output_dir or os.path.dirname(args.video_path)
        os.makedirs(out_dir, exist_ok=True)
        tmp_wav = tempfile.mktemp(suffix=".wav")
        extract_audio_track(args.video_path, tmp_wav, ar=args.ar, mono=True)
        items = read_srt(args.srt_path)
        csv_path = os.path.join(out_dir, f"{base}.sync_audit.csv")
        dbg_path = os.path.join(out_dir, f"{base}.sync_debug.log")
        write_sync_audit(tmp_wav, items, csv_path, dbg_path, win_ms=args.win_ms)
        print(csv_path)
        print(dbg_path)
        return 0
    if args.cmd == "rewrite":
        items = read_srt(args.srt_path)
        items = [SRTItem(i.start_ms, i.end_ms, apply_text_options(i.text, args.keep_brackets, args.strip_meta, args.strip_noise)) for i in items]
        from flexdub.core.subtitle import semantic_restructure
        items2 = semantic_restructure(items, max_chars=args.max_chars, max_duration_ms=args.max_duration)
        out = args.output
        if out is None:
            base = os.path.basename(args.srt_path)
            name, ext = os.path.splitext(base)
            out = os.path.join(os.path.dirname(args.srt_path), name + ".rewritten.srt")
        write_srt(out, items2)
        print(out)
        return 0
    if args.cmd == "fluency":
        items = read_srt(args.srt_path)
        items = [SRTItem(i.start_ms, i.end_ms, i.text) for i in items]
        from flexdub.core.subtitle import fluency_metrics
        score, breaks = fluency_metrics(items)
        print(f"TOTAL={score['total']}")
        print(f"TERMINAL_END_RATIO={score['terminal_end_ratio']:.3f}")
        print(f"BREAK_COUNT={score['break_count']}")
        if args.save:
            import csv
            with open(args.save, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["index", "prev_text", "next_text"]) 
                for idx, a, b in breaks:
                    w.writerow([idx, a, b])
            print(args.save)
        return 0
    if args.cmd == "qa":
        from flexdub.core.qa import run_qa_checks
        from flexdub.pipelines.elastic_video import validate_segment_lengths, TTS_CHAR_THRESHOLD
        
        report = run_qa_checks(
            args.srt_path,
            voice_map_path=args.voice_map,
            video_duration_ms=args.video_duration_ms,
            max_chars=args.max_chars,
            max_duration_ms=args.max_duration_ms
        )
        
        # TTS character length check
        tts_threshold = args.tts_char_threshold
        items = read_srt(args.srt_path)
        oversized_tts = validate_segment_lengths(items, tts_threshold, args.backend)
        
        # Print results
        print(f"[QA] SRT Valid: {report.srt_valid}")
        print(f"[QA] Speaker Coverage: {report.speaker_coverage:.1%}")
        if report.missing_speakers:
            print(f"[QA] Missing Speaker Tags: {report.missing_speakers[:10]}{'...' if len(report.missing_speakers) > 10 else ''}")
        print(f"[QA] Timeline Complete: {report.timeline_complete}")
        print(f"[QA] First Start: {report.first_start_ms}ms, Last End: {report.last_end_ms}ms")
        if report.max_chars_exceeded:
            print(f"[QA] Chars Exceeded ({args.max_chars}): {report.max_chars_exceeded[:10]}{'...' if len(report.max_chars_exceeded) > 10 else ''}")
        if report.max_duration_exceeded:
            print(f"[QA] Duration Exceeded ({args.max_duration_ms}ms): {report.max_duration_exceeded[:10]}{'...' if len(report.max_duration_exceeded) > 10 else ''}")
        
        # TTS character length results
        if oversized_tts:
            print(f"[QA] TTS Char Threshold ({tts_threshold}, backend={args.backend}): {len(oversized_tts)} segments exceeded")
            for seg_idx, char_count, preview in oversized_tts[:10]:
                print(f"[QA]   Segment {seg_idx}: {char_count} chars - {preview}")
            if len(oversized_tts) > 10:
                print(f"[QA]   ... and {len(oversized_tts) - 10} more")
        else:
            print(f"[QA] TTS Char Threshold ({tts_threshold}): OK")
        
        if args.voice_map:
            print(f"[QA] Voice Map Valid: {report.voice_map_valid}")
            print(f"[QA] Voice Map Has DEFAULT: {report.voice_map_has_default}")
        
        # Update all_passed to include TTS check
        all_passed = report.all_passed and len(oversized_tts) == 0
        print(f"[QA] ALL PASSED: {all_passed}")
        
        # Write report to file if requested
        if args.output:
            import json as _json
            report_dict = {
                "srt_valid": report.srt_valid,
                "speaker_coverage": report.speaker_coverage,
                "missing_speakers": report.missing_speakers,
                "timeline_complete": report.timeline_complete,
                "first_start_ms": report.first_start_ms,
                "last_end_ms": report.last_end_ms,
                "max_chars_exceeded": report.max_chars_exceeded,
                "max_duration_exceeded": report.max_duration_exceeded,
                "tts_char_threshold": tts_threshold,
                "tts_oversized_segments": [{"segment": s[0], "chars": s[1], "preview": s[2]} for s in oversized_tts],
                "voice_map_valid": report.voice_map_valid,
                "voice_map_has_default": report.voice_map_has_default,
                "all_passed": all_passed
            }
            with open(args.output, "w", encoding="utf-8") as f:
                _json.dump(report_dict, f, ensure_ascii=False, indent=2)
            print(f"[QA] Report written to: {args.output}")
        
        return 0 if all_passed else 1
    
    if args.cmd == "gs_align":
        from flexdub.core.gs_align import (
            parse_gs_md, align_gs_to_srt_v2, extract_glossary_from_gs,
            extract_speakers, calculate_coverage, SpeakerTracker
        )
        import json as _json
        
        # Read gs.md
        with open(args.gs_path, "r", encoding="utf-8") as f:
            gs_content = f.read()
        
        # Parse gs.md into paragraphs (extract speaker anchors)
        gs_paragraphs = parse_gs_md(gs_content)
        if not gs_paragraphs:
            print("[ERROR] No paragraphs found in gs.md")
            return 1
        
        # Extract speakers
        speakers = extract_speakers(gs_content)
        print(f"[GS_ALIGN] Parsed {len(gs_paragraphs)} anchors from gs.md")
        print(f"[GS_ALIGN] Found {len(speakers)} speakers: {speakers}")
        
        # Read original SRT for timeline
        srt_items = read_srt(args.srt_path)
        print(f"[GS_ALIGN] Read {len(srt_items)} items from SRT")
        
        # Calculate coverage stats
        coverage = calculate_coverage(gs_paragraphs, srt_items)
        print(f"[GS_ALIGN] Coverage: {coverage.coverage_percent:.1f}% ({coverage.covered_entries}/{coverage.total_entries})")
        print(f"[GS_ALIGN] Last anchor: {coverage.last_anchor_time}, Video duration: {coverage.video_duration}")
        
        if coverage.coverage_percent < 80:
            print(f"[GS_ALIGN] ⚠️  Warning: Coverage below 80%, some segments may use fallback")
        
        # Align: add speaker tags to original SRT (preserving original text)
        aligned_items = align_gs_to_srt_v2(
            gs_paragraphs,
            srt_items,
            max_chars=args.max_chars,
            include_speaker_tags=True
        )
        
        print(f"[GS_ALIGN] Generated {len(aligned_items)} aligned items (original count preserved)")
        
        # Determine output path
        out_path = args.output
        if out_path is None:
            base = os.path.splitext(os.path.basename(args.srt_path))[0]
            out_dir = os.path.dirname(args.srt_path)
            out_path = os.path.join(out_dir, base + ".audio.srt")
        
        # Write aligned SRT
        write_srt(out_path, aligned_items)
        print(f"[GS_ALIGN] Written: {out_path}")
        
        # Generate voice_map.json
        if speakers:
            voice_map_path = args.voice_map_output
            if voice_map_path is None:
                voice_map_path = os.path.join(os.path.dirname(out_path), "voice_map.json")
            
            # Generate voice_map with placeholder voices
            tracker = SpeakerTracker()
            voice_map = tracker.generate_voice_map(speakers)
            
            with open(voice_map_path, "w", encoding="utf-8") as f:
                _json.dump(voice_map, f, ensure_ascii=False, indent=2)
            print(f"[GS_ALIGN] Generated voice_map with {len(speakers)} speakers: {voice_map_path}")
            print(f"[GS_ALIGN] ⚠️  Please update voice_map.json with appropriate voices from: curl http://localhost:3456/speakers")
        
        # Extract glossary if requested
        if args.extract_glossary:
            glossary = extract_glossary_from_gs(gs_content)
            if glossary:
                glossary_path = args.glossary_output
                if glossary_path is None:
                    glossary_path = os.path.join(os.path.dirname(out_path), "glossary.yaml")
                
                # Write as YAML
                with open(glossary_path, "w", encoding="utf-8") as f:
                    f.write("# Auto-extracted glossary from gs.md\n")
                    f.write("# Format: English: 中文翻译\n\n")
                    for en, zh in sorted(glossary.items()):
                        f.write(f'"{en}": "{zh}"\n')
                print(f"[GS_ALIGN] Extracted {len(glossary)} terms to: {glossary_path}")
        
        return 0
    
    if args.cmd == "semantic_refine":
        from flexdub.core.semantic_refine import SemanticRefiner
        
        # Initialize refiner
        refiner = SemanticRefiner(
            api_key=args.api_key,
            base_url=args.base_url,
            model=args.model,
            checkpoint_dir=args.checkpoint_dir
        )
        
        # Determine output path
        out_path = args.output
        if out_path is None:
            base = os.path.splitext(os.path.basename(args.srt_path))[0]
            out_dir = os.path.dirname(args.srt_path)
            out_path = os.path.join(out_dir, base + ".refined.audio.srt")
        
        # Run refinement
        try:
            result = refiner.refine(
                gs_path=args.gs_path,
                srt_path=args.srt_path,
                output_path=out_path,
                include_speaker_tags=args.include_speaker_tags
            )
            
            print(f"\n[SEMANTIC_REFINE] 处理完成!")
            print(f"[SEMANTIC_REFINE] 总条目数: {result.item_count}")
            print(f"[SEMANTIC_REFINE] 已矫正条目数: {result.refined_count}")
            print(f"[SEMANTIC_REFINE] 术语数量: {len(result.terminology_used)}")
            print(f"[SEMANTIC_REFINE] 发现问题数: {result.issue_count}")
            print(f"[SEMANTIC_REFINE] 输出文件: {out_path}")
            
            return 0
        except FileNotFoundError as e:
            print(f"[ERROR] {e}")
            return 1
        except Exception as e:
            print(f"[ERROR] 处理失败: {e}")
            return 1
    
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
