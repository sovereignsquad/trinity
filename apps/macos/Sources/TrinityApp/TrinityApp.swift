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
    case governance
    case admin

    var id: String { rawValue }

    var title: String {
        switch self {
        case .overview: "Overview"
        case .timeline: "Timeline"
        case .candidates: "Candidates"
        case .feedback: "Feedback"
        case .governance: "Governance"
        case .admin: "Admin"
        }
    }

    var icon: String {
        switch self {
        case .overview: "circle.grid.2x2"
        case .timeline: "text.append"
        case .candidates: "sparkles.rectangle.stack"
        case .feedback: "checkmark.message"
        case .governance: "checklist"
        case .admin: "slider.horizontal.3"
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
        WindowGroup("trinity") {
            ContentView()
                .preferredColorScheme(themeMode.preferredColorScheme)
        }
        .defaultSize(width: 980, height: 680)

        Settings {
            TrinityAdminSettingsView()
                .preferredColorScheme(themeMode.preferredColorScheme)
        }
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
    @StateObject private var governanceStore = TrinityGovernanceStore()

    var body: some View {
        TrinityShell {
            NavigationSplitView {
                List(TrinityPage.allCases, selection: $selectedPage) { page in
                    Label(page.title, systemImage: page.icon)
                        .tag(page)
                }
                .navigationTitle("trinity")
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
        .task {
            if governanceStore.snapshots.isEmpty {
                await governanceStore.reload()
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                TrinitySectionHeader(
                    title: "trinity",
                    subtitle: "Candidate-runtime operator shell"
                )
                Spacer()
                TrinityStatusPill(label: "Scaffold active", color: TrinityPalette.info)
            }
            Text("This shell is aligned to the shared runtime language and is ready to host multiple downstream adapter surfaces.")
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
                    body: "Keep adapter payloads explicit and versioned instead of embedding product-specific UI assumptions.",
                    status: ("Multi-app ready", TrinityPalette.warning)
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
        case .governance:
            sectionPanel(
                title: "Governance",
                subtitle: "Latest release, triage, and override lineage from persisted runtime artifacts."
            ) {
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Adapter governance status")
                            .font(.headline)
                        Spacer()
                        Button("Refresh") {
                            Task {
                                await governanceStore.reload()
                            }
                        }
                        .disabled(governanceStore.isLoading)
                    }
                    if governanceStore.isLoading && governanceStore.snapshots.isEmpty {
                        TrinityLoadingState(title: "Loading persisted governance artifacts...")
                    }
                    if let loadErrorMessage = governanceStore.loadErrorMessage {
                        TrinityInlineBanner(
                            title: "Partial artifact load failure",
                            bodyText: loadErrorMessage,
                            color: TrinityPalette.warning
                        )
                    }
                    if !governanceStore.isLoading && governanceStore.snapshots.isEmpty {
                        TrinityEmptyState(
                            title: "No governance artifacts yet",
                            bodyText: "The shell did not find persisted runtime governance data in the local Trinity app-support directory."
                        )
                    } else {
                        ForEach(governanceStore.snapshots) { snapshot in
                            governanceSnapshotCard(snapshot)
                        }
                    }
                }
            }
        case .admin:
            TrinityAdminSettingsView(showsOwnScrollView: false)
        }
    }

    private func sectionPanel<Content: View>(title: String, subtitle: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            TrinitySectionHeader(title: title, subtitle: subtitle)
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

    private func governanceSnapshotCard(_ snapshot: TrinityGovernanceSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(snapshot.adapterName.uppercased())
                        .font(.headline)
                    Text("Latest report: \(snapshot.latestReportID)")
                        .foregroundStyle(TrinityPalette.textSecondary)
                }
                Spacer()
                TrinityStatusPill(
                    label: governanceStateLabel(snapshot.readStatus),
                    color: governanceStateColor(snapshot.readStatus)
                )
                TrinityStatusPill(
                    label: snapshot.latestReleaseStatus == "none" ? "No release call" : snapshot.latestReleaseStatus,
                    color: snapshot.latestReleaseStatus == "approve" ? TrinityPalette.success : TrinityPalette.warning
                )
            }
            TrinityInlineBanner(
                title: governanceStateTitle(snapshot.readStatus),
                bodyText: snapshot.statusDetail,
                color: governanceStateColor(snapshot.readStatus)
            )
            HStack {
                TrinityStatusPill(label: "Review \(snapshot.latestReviewStatus)", color: TrinityPalette.info)
                TrinityStatusPill(
                    label: "\(snapshot.openTriageItemCount) open triage",
                    color: snapshot.openTriageItemCount == 0 ? TrinityPalette.success : TrinityPalette.warning
                )
                TrinityStatusPill(label: "\(snapshot.resolvedTriageCount) resolved", color: TrinityPalette.success)
            }
            if !snapshot.topOpenTriageSummaries.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Top open work")
                        .font(.subheadline.weight(.semibold))
                    ForEach(snapshot.topOpenTriageSummaries, id: \.self) { summary in
                        Text(summary)
                            .foregroundStyle(TrinityPalette.textSecondary)
                    }
                }
            }
            if !snapshot.artifacts.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Accepted artifacts")
                        .font(.subheadline.weight(.semibold))
                    ForEach(snapshot.artifacts) { artifact in
                        HStack {
                            Text("\(artifact.id) \(artifact.version)")
                            Spacer()
                            TrinityStatusPill(label: artifact.scoreStatus, color: TrinityPalette.info)
                            TrinityStatusPill(label: artifact.releaseStatus, color: TrinityPalette.warning)
                            if artifact.overrideCount > 0 {
                                TrinityStatusPill(label: "\(artifact.overrideCount) override", color: TrinityPalette.warning)
                            }
                        }
                    }
                }
            }
        }
        .trinityPanel()
    }

    private func governanceStateLabel(_ status: TrinityGovernanceReadStatus) -> String {
        switch status {
        case .loaded: "Loaded"
        case .missing: "Missing"
        case .failed: "Read failed"
        }
    }

    private func governanceStateTitle(_ status: TrinityGovernanceReadStatus) -> String {
        switch status {
        case .loaded: "Artifacts available"
        case .missing: "No local artifact history"
        case .failed: "Artifact read problem"
        }
    }

    private func governanceStateColor(_ status: TrinityGovernanceReadStatus) -> Color {
        switch status {
        case .loaded: TrinityPalette.success
        case .missing: TrinityPalette.info
        case .failed: TrinityPalette.warning
        }
    }
}
