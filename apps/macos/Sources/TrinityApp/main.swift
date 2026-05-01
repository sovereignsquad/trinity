import SwiftUI

@main
struct TrinityApp: App {
    var body: some Scene {
        WindowGroup("Trinity") {
            ContentView()
        }
        .defaultSize(width: 980, height: 680)
    }
}

struct ContentView: View {
    var body: some View {
        NavigationSplitView {
            List {
                Label("Overview", systemImage: "circle.grid.2x2")
                Label("Timeline", systemImage: "text.append")
                Label("Candidates", systemImage: "sparkles.rectangle.stack")
                Label("Feedback", systemImage: "checkmark.message")
            }
            .navigationTitle("Trinity")
        } detail: {
            VStack(alignment: .leading, spacing: 16) {
                Text("Trinity")
                    .font(.largeTitle.weight(.semibold))
                Text("Local-first candidate workflow scaffold")
                    .font(.title3)
                    .foregroundStyle(.secondary)
                Divider()
                Text("This shell establishes the native development baseline for the runtime workflow.")
                    .foregroundStyle(.secondary)
                Spacer()
            }
            .padding(24)
        }
    }
}

