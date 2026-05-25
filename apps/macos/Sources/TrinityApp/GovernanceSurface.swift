import Foundation
import SwiftUI

enum TrinityGovernanceReadStatus: String {
    case loaded
    case missing
    case failed
}

struct TrinityGovernanceArtifactSummary: Identifiable {
    let id: String
    let version: String
    let scoreStatus: String
    let releaseStatus: String
    let overrideCount: Int
}

struct TrinityGovernanceSnapshot: Identifiable {
    let id: String
    let adapterName: String
    let readStatus: TrinityGovernanceReadStatus
    let statusDetail: String
    let latestReportID: String
    let latestReviewStatus: String
    let latestReleaseStatus: String
    let openTriageItemCount: Int
    let resolvedTriageCount: Int
    let topOpenTriageSummaries: [String]
    let artifacts: [TrinityGovernanceArtifactSummary]
}

@MainActor
final class TrinityGovernanceStore: ObservableObject {
    @Published private(set) var snapshots: [TrinityGovernanceSnapshot] = []
    @Published private(set) var isLoading = false
    @Published private(set) var lastLoadedAt: Date?
    @Published private(set) var loadErrorMessage: String?

    func reload() async {
        isLoading = true
        loadErrorMessage = nil

        let adapterNames = TrinityAdapterCatalog.availableAdapters().map(\.adapterName)
        let loadedSnapshots = await Task.detached(priority: .userInitiated) {
            TrinityGovernanceLoader.loadAll(adapterNames: adapterNames)
        }.value

        snapshots = loadedSnapshots
        lastLoadedAt = Date()
        isLoading = false

        let failedSnapshots = loadedSnapshots.filter { $0.readStatus == .failed }
        if !failedSnapshots.isEmpty {
            loadErrorMessage = "Some governance artifacts could not be read. Inspect the affected adapter cards for details."
        }
    }
}

enum TrinityGovernanceLoader {
    static func loadAll(adapterNames: [String]) -> [TrinityGovernanceSnapshot] {
        adapterNames.map(loadSnapshot(adapterName:))
    }

    private static func loadSnapshot(adapterName: String) -> TrinityGovernanceSnapshot {
        let adapterRoot = runtimeRoot().appendingPathComponent(adapterName)
        guard FileManager.default.fileExists(atPath: adapterRoot.path) else {
            return TrinityGovernanceSnapshot(
                id: adapterName,
                adapterName: adapterName,
                readStatus: .missing,
                statusDetail: "No persisted runtime artifacts found for this adapter yet.",
                latestReportID: "No report",
                latestReviewStatus: "none",
                latestReleaseStatus: "none",
                openTriageItemCount: 0,
                resolvedTriageCount: 0,
                topOpenTriageSummaries: [],
                artifacts: []
            )
        }

        let evalRoot = adapterRoot.appendingPathComponent("eval_datasets")
        var loadIssues: [String] = []

        let latestReport = latestJSON(
            in: evalRoot.appendingPathComponent("score_health_reports"),
            label: "score health report",
            issues: &loadIssues
        )
        let latestDecision = latestJSON(
            in: evalRoot.appendingPathComponent("score_health_review_decisions"),
            label: "score health review decision",
            issues: &loadIssues
        )
        let latestReleaseDecision = latestJSON(
            in: evalRoot.appendingPathComponent("score_governance_release_decisions"),
            label: "release decision",
            issues: &loadIssues
        )
        let latestTriage = latestJSON(
            in: evalRoot.appendingPathComponent("score_governance_triage_reports"),
            label: "triage report",
            issues: &loadIssues
        )
        let resolutions = allJSON(
            in: evalRoot.appendingPathComponent("score_governance_triage_resolutions"),
            label: "triage resolution",
            issues: &loadIssues
        )

        let openTriageSummaries =
            (latestTriage["items"] as? [[String: Any]] ?? []).prefix(3).compactMap {
                $0["summary"] as? String
            }

        let artifactsResult = loadArtifactSummaries(adapterRoot: adapterRoot)
        loadIssues.append(contentsOf: artifactsResult.issues)

        let readStatus: TrinityGovernanceReadStatus = loadIssues.isEmpty ? .loaded : .failed
        let statusDetail =
            loadIssues.isEmpty
            ? "Governance artifacts loaded successfully."
            : loadIssues.joined(separator: " ")

        return TrinityGovernanceSnapshot(
            id: adapterName,
            adapterName: adapterName,
            readStatus: readStatus,
            statusDetail: statusDetail,
            latestReportID: (latestReport["report_id"] as? String) ?? "No report",
            latestReviewStatus: (latestDecision["status"] as? String) ?? "none",
            latestReleaseStatus: (latestReleaseDecision["decision_status"] as? String) ?? "none",
            openTriageItemCount: (latestTriage["item_count"] as? Int) ?? 0,
            resolvedTriageCount: resolutions.filter {
                guard let status = $0["resolution_status"] as? String else { return false }
                return status == "resolved" || status == "known_noise"
            }.count,
            topOpenTriageSummaries: openTriageSummaries,
            artifacts: artifactsResult.artifacts
        )
    }

    private static func loadArtifactSummaries(adapterRoot: URL) -> (
        artifacts: [TrinityGovernanceArtifactSummary],
        issues: [String]
    ) {
        let artifactsRoot = adapterRoot.appendingPathComponent("accepted_artifacts/artifacts")
        guard FileManager.default.fileExists(atPath: artifactsRoot.path) else {
            return ([], [])
        }
        guard let artifactDirs = try? FileManager.default.contentsOfDirectory(
            at: artifactsRoot,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        ) else {
            return ([], ["Accepted artifact directory could not be listed."])
        }
        var issues: [String] = []
        let artifacts: [TrinityGovernanceArtifactSummary] = artifactDirs
            .compactMap { artifactDir in
                let currentPath = artifactDir.appendingPathComponent("current.json")
                let payload = loadJSON(
                    at: currentPath,
                    label: "accepted artifact \(artifactDir.lastPathComponent)",
                    issues: &issues
                )
                guard
                    let artifact = payload["artifact"] as? [String: Any],
                    let artifactKey = artifact["artifact_key"] as? String,
                    let version = artifact["version"] as? String
                else {
                    return nil
                }
                let overrideNotes = payload["score_governance_override_notes"] as? [Any] ?? []
                return TrinityGovernanceArtifactSummary(
                    id: artifactKey,
                    version: version,
                    scoreStatus: (payload["score_governance_status"] as? String) ?? "none",
                    releaseStatus: (payload["release_governance_decision_status"] as? String) ?? "none",
                    overrideCount: overrideNotes.count
                )
            }
            .sorted { left, right in
                left.id < right.id
            }
        return (artifacts, issues)
    }

    private static func runtimeRoot() -> URL {
        if let override = ProcessInfo.processInfo.environment["TRINITY_APP_SUPPORT_DIR"],
            !override.isEmpty
        {
            return URL(fileURLWithPath: override)
                .appendingPathComponent("trinity_runtime/adapters")
        }
        let appSupport =
            FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support")
        return appSupport.appendingPathComponent("Trinity/trinity_runtime/adapters")
    }

    private static func latestJSON(
        in directory: URL,
        label: String,
        issues: inout [String]
    ) -> [String: Any] {
        let payloads = allJSON(in: directory, label: label, issues: &issues)
        return payloads.last ?? [:]
    }

    private static func allJSON(
        in directory: URL,
        label: String,
        issues: inout [String]
    ) -> [[String: Any]] {
        guard FileManager.default.fileExists(atPath: directory.path) else {
            return []
        }
        guard let files = try? FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: [.contentModificationDateKey],
            options: [.skipsHiddenFiles]
        ) else {
            issues.append("\(label.capitalized) directory could not be listed.")
            return []
        }
        let sortedFiles = files.sorted {
            let leftDate =
                (try? $0.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate)
                ?? .distantPast
            let rightDate =
                (try? $1.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate)
                ?? .distantPast
            if leftDate == rightDate {
                return $0.lastPathComponent < $1.lastPathComponent
            }
            return leftDate < rightDate
        }
        return sortedFiles.map { loadJSON(at: $0, label: label, issues: &issues) }
    }

    private static func loadJSON(
        at path: URL,
        label: String,
        issues: inout [String]
    ) -> [String: Any] {
        do {
            let data = try Data(contentsOf: path)
            let payload = try JSONSerialization.jsonObject(with: data)
            guard let dictionary = payload as? [String: Any] else {
                issues.append("\(label.capitalized) at \(path.lastPathComponent) is not a JSON object.")
                return [:]
            }
            return dictionary
        } catch {
            issues.append("\(label.capitalized) at \(path.lastPathComponent) failed to load: \(error.localizedDescription).")
            return [:]
        }
    }
}
