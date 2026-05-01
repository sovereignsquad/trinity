import SwiftUI

private enum TrinityThemeMode: String, CaseIterable {
    case system
    case light
    case dark

    var label: String {
        switch self {
        case .system: "Follow System"
        case .light: "Light"
        case .dark: "Dark"
        }
    }

    var preferredColorScheme: ColorScheme? {
        switch self {
        case .system: nil
        case .light: .light
        case .dark: .dark
        }
    }
}

private enum TrinityPage: String, CaseIterable, Identifiable {
    case overview
    case timeline
    case candidates
    case feedback

    var id: String { rawValue }

    var title: String {
        switch self {
        case .overview: "Overview"
        case .timeline: "Timeline"
        case .candidates: "Candidates"
        case .feedback: "Feedback"
        }
    }

    var icon: String {
        switch self {
        case .overview: "circle.grid.2x2"
        case .timeline: "text.append"
        case .candidates: "sparkles.rectangle.stack"
        case .feedback: "checkmark.message"
        }
    }
}

@main
struct TrinityApp: App {
    @AppStorage("trinity.theme.mode") private var themeModeRawValue = TrinityThemeMode.system.rawValue

    private var themeMode: TrinityThemeMode {
        get { TrinityThemeMode(rawValue: themeModeRawValue) ?? .system }
        set { themeModeRawValue = newValue.rawValue }
    }

    var body: some Scene {
        WindowGroup("Trinity") {
            ContentView()
                .preferredColorScheme(themeMode.preferredColorScheme)
        }
        .defaultSize(width: 980, height: 680)
        .commands {
            CommandMenu("Theme") {
                ForEach(TrinityThemeMode.allCases, id: \.rawValue) { mode in
                    Button(mode.label) {
                        themeModeRawValue = mode.rawValue
                    }
                }
            }
        }
    }
}

struct ContentView: View {
    @State private var selectedPage: TrinityPage? = .overview

    var body: some View {
        TrinityShell {
            NavigationSplitView {
                List(TrinityPage.allCases, selection: $selectedPage) { page in
                    Label(page.title, systemImage: page.icon)
                        .tag(page)
                }
                .navigationTitle("Trinity")
                .navigationSplitViewColumnWidth(min: 180, ideal: 220)
                .scrollContentBackground(.hidden)
            } detail: {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        header
                        detailContent
                    }
                    .padding(24)
                }
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Trinity")
                        .font(.largeTitle.weight(.bold))
                        .foregroundStyle(TrinityPalette.textPrimary)
                    Text("Candidate-runtime operator shell")
                        .font(.title3)
                        .foregroundStyle(TrinityPalette.textSecondary)
                }
                Spacer()
                TrinityStatusPill(label: "Scaffold active", color: TrinityPalette.info)
            }
            Text("This shell is now aligned to the shared operator language and is ready to host the runtime workflow surfaces.")
                .foregroundStyle(TrinityPalette.textSecondary)
        }
        .trinityPanel()
    }

    @ViewBuilder
    private var detailContent: some View {
        switch selectedPage ?? .overview {
        case .overview:
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                summaryCard(
                    title: "Evidence intake",
                    body: "Normalize incoming product evidence into runtime-ready envelopes.",
                    status: ("Ready for adapter work", TrinityPalette.success)
                )
                summaryCard(
                    title: "Frontier selection",
                    body: "Rank candidate sets and surface the active frontier for execution.",
                    status: ("Bounded for train", TrinityPalette.info)
                )
                summaryCard(
                    title: "Feedback memory",
                    body: "Persist operator feedback without leaking product-specific behavior into runtime code.",
                    status: ("Runtime owned", TrinityPalette.success)
                )
                summaryCard(
                    title: "Product contract",
                    body: "Keep reply-facing payloads explicit and versioned instead of embedding UI assumptions.",
                    status: ("v1 adapter path", TrinityPalette.warning)
                )
            }
        case .timeline:
            sectionPanel(
                title: "Timeline",
                subtitle: "Lifecycle stages for the runtime candidate workflow."
            ) {
                VStack(alignment: .leading, spacing: 12) {
                    timelineRow("1", "Ingest evidence", "Product signals enter the runtime through explicit integration envelopes.")
                    timelineRow("2", "Generate candidates", "Candidate generation stays runtime-owned, not product-owned.")
                    timelineRow("3", "Evaluate frontier", "Selection and suppression logic produce the next actionable set.")
                    timelineRow("4", "Capture feedback", "Accepted and rejected outcomes feed durable runtime memory.")
                }
            }
        case .candidates:
            sectionPanel(
                title: "Candidates",
                subtitle: "Runtime state classes the UI should eventually surface."
            ) {
                VStack(alignment: .leading, spacing: 12) {
                    summaryCard(title: "Proposed", body: "New candidate waiting for evaluation.", status: ("Queued", TrinityPalette.info))
                    summaryCard(title: "Frontier", body: "Candidate currently selected for product execution.", status: ("Active", TrinityPalette.success))
                    summaryCard(title: "Suppressed", body: "Candidate intentionally withheld by runtime policy.", status: ("Hidden", TrinityPalette.warning))
                }
            }
        case .feedback:
            sectionPanel(
                title: "Feedback",
                subtitle: "Operator signals that need consistent semantics across apps."
            ) {
                VStack(alignment: .leading, spacing: 12) {
                    feedbackRow("Accepted", TrinityPalette.success, "Outcome promoted and may inform future runtime memory.")
                    feedbackRow("Rejected", TrinityPalette.warning, "Outcome preserved for learning without product-side drift.")
                    feedbackRow("Blocked", TrinityPalette.info, "Execution deferred pending external data or policy checks.")
                }
            }
        }
    }

    private func sectionPanel<Content: View>(title: String, subtitle: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(title)
                .font(.title3.weight(.semibold))
            Text(subtitle)
                .foregroundStyle(TrinityPalette.textSecondary)
            content()
        }
        .trinityPanel()
    }

    private func summaryCard(title: String, body: String, status: (String, Color)) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(title)
                    .font(.headline)
                Spacer()
                TrinityStatusPill(label: status.0, color: status.1)
            }
            Text(body)
                .foregroundStyle(TrinityPalette.textSecondary)
        }
        .trinityPanel()
    }

    private func timelineRow(_ step: String, _ title: String, _ body: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(step)
                .font(.caption.weight(.bold))
                .foregroundStyle(TrinityPalette.textPrimary)
                .frame(width: 26, height: 26)
                .background(TrinityPalette.panelAlt)
                .clipShape(Circle())
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .fontWeight(.semibold)
                Text(body)
                    .foregroundStyle(TrinityPalette.textSecondary)
            }
        }
    }

    private func feedbackRow(_ title: String, _ color: Color, _ body: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            TrinityStatusPill(label: title, color: color)
            Text(body)
                .foregroundStyle(TrinityPalette.textSecondary)
        }
    }
}
