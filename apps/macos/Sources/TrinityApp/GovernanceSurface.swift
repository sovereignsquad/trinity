import Foundation

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
    let latestReportID: String
    let latestReviewStatus: String
    let latestReleaseStatus: String
    let openTriageItemCount: Int
    let resolvedTriageCount: Int
    let topOpenTriageSummaries: [String]
    let artifacts: [TrinityGovernanceArtifactSummary]
}

enum TrinityGovernanceLoader {
    static func loadAll() -> [TrinityGovernanceSnapshot] {
        ["reply", "spot"].map(loadSnapshot(adapterName:))
    }

    private static func loadSnapshot(adapterName: String) -> TrinityGovernanceSnapshot {
        let adapterRoot = runtimeRoot().appendingPathComponent(adapterName)
        let evalRoot = adapterRoot.appendingPathComponent("eval_datasets")

        let latestReport = latestJSON(in: evalRoot.appendingPathComponent("score_health_reports"))
        let latestDecision = latestJSON(
            in: evalRoot.appendingPathComponent("score_health_review_decisions")
        )
        let latestReleaseDecision = latestJSON(
            in: evalRoot.appendingPathComponent("score_governance_release_decisions")
        )
        let latestTriage = latestJSON(
            in: evalRoot.appendingPathComponent("score_governance_triage_reports")
        )
        let resolutions = allJSON(
            in: evalRoot.appendingPathComponent("score_governance_triage_resolutions")
        )

        let openTriageSummaries =
            (latestTriage["items"] as? [[String: Any]] ?? []).prefix(3).compactMap {
                $0["summary"] as? String
            }

        return TrinityGovernanceSnapshot(
            id: adapterName,
            adapterName: adapterName,
            latestReportID: (latestReport["report_id"] as? String) ?? "No report",
            latestReviewStatus: (latestDecision["status"] as? String) ?? "none",
            latestReleaseStatus: (latestReleaseDecision["decision_status"] as? String) ?? "none",
            openTriageItemCount: (latestTriage["item_count"] as? Int) ?? 0,
            resolvedTriageCount: resolutions.filter {
                guard let status = $0["resolution_status"] as? String else { return false }
                return status == "resolved" || status == "known_noise"
            }.count,
            topOpenTriageSummaries: openTriageSummaries,
            artifacts: loadArtifactSummaries(adapterRoot: adapterRoot)
        )
    }

    private static func loadArtifactSummaries(adapterRoot: URL) -> [TrinityGovernanceArtifactSummary] {
        let artifactsRoot = adapterRoot.appendingPathComponent("accepted_artifacts/artifacts")
        guard let artifactDirs = try? FileManager.default.contentsOfDirectory(
            at: artifactsRoot,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        ) else {
            return []
        }
        return artifactDirs.compactMap { artifactDir in
            let currentPath = artifactDir.appendingPathComponent("current.json")
            let payload = loadJSON(at: currentPath)
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
        .sorted { $0.id < $1.id }
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

    private static func latestJSON(in directory: URL) -> [String: Any] {
        let payloads = allJSON(in: directory)
        return payloads.last ?? [:]
    }

    private static func allJSON(in directory: URL) -> [[String: Any]] {
        guard let files = try? FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: [.contentModificationDateKey],
            options: [.skipsHiddenFiles]
        ) else {
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
        return sortedFiles.map(loadJSON(at:))
    }

    private static func loadJSON(at path: URL) -> [String: Any] {
        guard
            let data = try? Data(contentsOf: path),
            let payload = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return [:]
        }
        return payload
    }
}
