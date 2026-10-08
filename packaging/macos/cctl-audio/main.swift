// cctl-audio: capture system audio (or the microphone) on macOS with ScreenCaptureKit and write a WAV file.
//
// Launched by cctl through LaunchServices (`open -W -n -g -a cctl-audio.app --args ...`) so that the
// Screen & System Audio Recording / Microphone permissions belong to this small app, not to whatever
// terminal or agent harness started cctl.
//
//   cctl-audio --out FILE.wav [--mic] [--max-seconds N] [--stop-file PATH]
//
// Writes FILE.wav.started once capture is running (or FILE.wav.error with a message), then records until
// --stop-file appears or --max-seconds elapse. Output is the stream's native PCM (48 kHz float32).

import AVFoundation
import CoreMedia
import Foundation
import ScreenCaptureKit

final class Recorder: NSObject, SCStreamOutput, SCStreamDelegate {
    let url: URL
    let mic: Bool
    var file: AVAudioFile?
    var frames: Int64 = 0

    init(url: URL, mic: Bool) {
        self.url = url
        self.mic = mic
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer, of type: SCStreamOutputType) {
        let wanted: SCStreamOutputType
        if #available(macOS 15.0, *), mic { wanted = .microphone } else { wanted = .audio }
        guard type == wanted, sb.isValid,
              let desc = CMSampleBufferGetFormatDescription(sb),
              let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(desc),
              let fmt = AVAudioFormat(streamDescription: asbd) else { return }
        let count = AVAudioFrameCount(CMSampleBufferGetNumSamples(sb))
        guard count > 0, let pcm = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: count) else { return }
        pcm.frameLength = count
        let status = CMSampleBufferCopyPCMDataIntoAudioBufferList(
            sb, at: 0, frameCount: Int32(count), into: pcm.mutableAudioBufferList)
        guard status == noErr else { return }
        do {
            if file == nil {
                file = try AVAudioFile(forWriting: url, settings: fmt.settings, commonFormat: fmt.commonFormat,
                                       interleaved: fmt.isInterleaved)
            }
            try file?.write(from: pcm)
            frames += Int64(count)
        } catch {
            fputs("write failed: \(error)\n", stderr)
        }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        fputs("stream stopped: \(error)\n", stderr)
    }
}

final class NullScreen: NSObject, SCStreamOutput {
    func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer, of type: SCStreamOutputType) {}
}

func mark(_ path: String, _ suffix: String, _ text: String = "") {
    try? text.write(toFile: path + suffix, atomically: true, encoding: .utf8)
}

@main
struct Main {
    static func main() async {
        var out = "", mic = false, maxSeconds = 600.0, stopFile = ""
        var args = CommandLine.arguments.dropFirst().makeIterator()
        while let a = args.next() {
            switch a {
            case "--out": out = args.next() ?? ""
            case "--mic": mic = true
            case "--max-seconds": maxSeconds = Double(args.next() ?? "") ?? 600
            case "--stop-file": stopFile = args.next() ?? ""
            default: break
            }
        }
        guard !out.isEmpty else {
            fputs("usage: cctl-audio --out FILE.wav [--mic] [--max-seconds N] [--stop-file PATH]\n", stderr)
            exit(64)
        }
        if mic, #unavailable(macOS 15.0) {
            mark(out, ".error", "microphone capture needs macOS 15 or later")
            exit(2)
        }
        do {
            let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
            guard let display = content.displays.first else {
                mark(out, ".error", "no display to attach the audio stream to")
                exit(2)
            }
            let cfg = SCStreamConfiguration()
            cfg.capturesAudio = !mic
            cfg.excludesCurrentProcessAudio = true
            cfg.sampleRate = 48000
            cfg.channelCount = 2
            cfg.width = 2
            cfg.height = 2
            cfg.minimumFrameInterval = CMTime(value: 1, timescale: 1)
            if #available(macOS 15.0, *) { cfg.captureMicrophone = mic }

            let rec = Recorder(url: URL(fileURLWithPath: out), mic: mic)
            let screen = NullScreen()
            let stream = SCStream(filter: SCContentFilter(display: display, excludingWindows: []),
                                  configuration: cfg, delegate: rec)
            let queue = DispatchQueue(label: "cctl-audio")
            try stream.addStreamOutput(screen, type: .screen, sampleHandlerQueue: queue)
            if #available(macOS 15.0, *), mic {
                try stream.addStreamOutput(rec, type: .microphone, sampleHandlerQueue: queue)
            } else {
                try stream.addStreamOutput(rec, type: .audio, sampleHandlerQueue: queue)
            }
            try await stream.startCapture()
            mark(out, ".started")
            let t0 = Date()
            while Date().timeIntervalSince(t0) < maxSeconds {
                if !stopFile.isEmpty && FileManager.default.fileExists(atPath: stopFile) { break }
                try await Task.sleep(nanoseconds: 50_000_000)
            }
            try await stream.stopCapture()
            queue.sync {}
            mark(out, ".done", "\(rec.frames)")
            exit(0)
        } catch {
            mark(out, ".error", "\(error.localizedDescription)")
            exit(1)
        }
    }
}
