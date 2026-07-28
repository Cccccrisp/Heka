import AppKit
import WebKit

@main
struct HekaDesktop {
    private static let delegate = AppDelegate()

    static func main() {
        let app = NSApplication.shared
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.activate(ignoringOtherApps: true)
        app.run()
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private let webView = WKWebView()
    private var server: Process?
    private var outputPipe: Pipe?
    private lazy var logURL: URL = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        .appendingPathComponent("Heka/desktop-launcher.log")

    private func log(_ message: String) {
        let line = "[\(Date())] \(message)\n"
        let directory = logURL.deletingLastPathComponent()
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        if FileManager.default.fileExists(atPath: logURL.path) {
            if let handle = try? FileHandle(forWritingTo: logURL) {
                _ = try? handle.seekToEnd()
                try? handle.write(contentsOf: Data(line.utf8))
                try? handle.close()
            }
        } else {
            try? Data(line.utf8).write(to: logURL)
        }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1320, height: 860),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Heka"
        window.center()
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        startServer()
    }

    private func startServer() {
        log("Launching desktop shell")
        guard let resources = Bundle.main.resourceURL else { showError("找不到 Heka 的本地文件。"); return }
        let project = resources.appendingPathComponent("heka", isDirectory: true)
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Heka", isDirectory: true)
        try? FileManager.default.createDirectory(at: appSupport, withIntermediateDirectories: true)

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["python3", "server.py"]
        process.currentDirectoryURL = project
        var environment = ProcessInfo.processInfo.environment
        environment["HEKA_PORT"] = "0"
        environment["HEKA_OPEN_BROWSER"] = "0"
        environment["HEKA_DATA_DIR"] = appSupport.path
        environment["HEKA_CONFIG_FILE"] = appSupport.appendingPathComponent(".env").path
        process.environment = environment

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard let text = String(data: data, encoding: .utf8), !text.isEmpty else { return }
            self?.log("server: \(text.trimmingCharacters(in: .whitespacesAndNewlines))")
            for line in text.split(separator: "\n") where line.hasPrefix("HEKA_READY=") {
                let address = String(line.dropFirst("HEKA_READY=".count))
                DispatchQueue.main.async {
                    self?.webView.load(URLRequest(url: URL(string: address)!))
                }
            }
        }

        do {
            try process.run()
            process.terminationHandler = { [weak self] finished in
                self?.log("server exited with status \(finished.terminationStatus)")
            }
            server = process
            outputPipe = pipe
        } catch {
            log("server launch error: \(error.localizedDescription)")
            showError("Heka 没能启动。请确认你的 Mac 已安装 Python 3。")
        }
    }

    private func showError(_ message: String) {
        webView.loadHTMLString("<main style='font: 18px -apple-system; padding: 48px; color: #202223'><h1>Heka 无法启动</h1><p>\(message)</p></main>", baseURL: nil)
    }

    func applicationWillTerminate(_ notification: Notification) {
        server?.terminate()
    }
}
