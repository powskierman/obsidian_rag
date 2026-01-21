import Cocoa
import SwiftUI

// Config
let windowWidth: CGFloat = 400
let windowMinHeight: CGFloat = 200

// Custom TextView to handle shortcuts reliably
class CaptureTextView: NSTextView {
    var onSave: (() -> Void)?
    
    override func keyDown(with event: NSEvent) {
        // Check for Cmd + Enter
        // 36 is Return, 76 is Enter on numpad
        if event.modifierFlags.contains(.command) && (event.keyCode == 36 || event.keyCode == 76) {
            onSave?()
            return
        }
        super.keyDown(with: event)
    }
}

class CaptureAppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var textView: CaptureTextView!
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Ensure app is active and has focus capability
        NSApp.setActivationPolicy(.regular)
        
        // Create Window
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: windowWidth, height: windowMinHeight),
            styleMask: [.titled, .closable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.center()
        window.title = "Capture to Second Brain"
        window.backgroundColor = NSColor(red: 1.0, green: 0.98, blue: 0.8, alpha: 1.0) // Sticky Note Yellow
        window.level = .floating // Keep on top
        
        // Scroll View
        let scrollView = NSScrollView(frame: window.contentView!.bounds)
        scrollView.autoresizingMask = [.width, .height]
        scrollView.hasVerticalScroller = true
        scrollView.borderType = .noBorder
        scrollView.drawsBackground = false
        
        // Custom Text View
        textView = CaptureTextView(frame: scrollView.bounds)
        textView.autoresizingMask = [.width]
        textView.font = NSFont.systemFont(ofSize: 18)
        
        // FORCE COLORS
        textView.backgroundColor = .clear 
        textView.textColor = NSColor.black 
        textView.insertionPointColor = NSColor.black
        
        textView.isRichText = false
        textView.allowsUndo = true
        
        // Handle Save Action
        textView.onSave = { [weak self] in
            self?.saveAndExit()
        }
        
        // Add some padding
        textView.textContainerInset = NSSize(width: 10, height: 10)
        
        scrollView.documentView = textView
        window.contentView?.addSubview(scrollView)
        
        // Show Window and Force Focus
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        window.makeFirstResponder(textView)
        
        // Brute force focus
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            NSApp.activate(ignoringOtherApps: true)
            self.window.makeFirstResponder(self.textView)
        }
    }
    
    func saveAndExit() {
        if let content = textView.string.data(using: .utf8) {
            FileHandle.standardOutput.write(content)
        }
        NSApp.terminate(nil)
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

// Main Entry Point
let app = NSApplication.shared
let delegate = CaptureAppDelegate()
app.delegate = delegate
app.run()