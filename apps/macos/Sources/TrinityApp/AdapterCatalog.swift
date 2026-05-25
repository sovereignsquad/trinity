import Foundation

struct TrinityUIAdapterDescriptor: Identifiable, Hashable {
    let adapterName: String
    let displayName: String
    let summary: String
    let supportsSettingsUI: Bool

    var id: String { adapterName }
}

enum TrinityAdapterCatalog {
    static let builtInAdapters: [TrinityUIAdapterDescriptor] = [
        TrinityUIAdapterDescriptor(
            adapterName: "reply",
            displayName: "Reply",
            summary: "Mature drafting adapter and policy workflow.",
            supportsSettingsUI: true
        ),
        TrinityUIAdapterDescriptor(
            adapterName: "spot",
            displayName: "Spot",
            summary: "Bounded reasoning and review adapter.",
            supportsSettingsUI: true
        ),
    ]

    static func availableAdapters() -> [TrinityUIAdapterDescriptor] {
        let discovered = Set(discoveredAdapterNames())
        var descriptorsByName = Dictionary(
            uniqueKeysWithValues: builtInAdapters.map { ($0.adapterName, $0) }
        )
        for adapterName in discovered where descriptorsByName[adapterName] == nil {
            descriptorsByName[adapterName] = TrinityUIAdapterDescriptor(
                adapterName: adapterName,
                displayName: adapterName.capitalized,
                summary: "Detected runtime adapter without a dedicated macOS settings surface yet.",
                supportsSettingsUI: false
            )
        }
        return descriptorsByName.values.sorted { $0.adapterName < $1.adapterName }
    }

    static func configurableAdapters() -> [TrinityUIAdapterDescriptor] {
        availableAdapters().filter(\.supportsSettingsUI)
    }

    static func unsupportedAdaptersForSettings() -> [TrinityUIAdapterDescriptor] {
        availableAdapters().filter { !$0.supportsSettingsUI }
    }

    static func runtimeRoot() -> URL {
        if let override = ProcessInfo.processInfo.environment["TRINITY_APP_SUPPORT_DIR"],
           !override.isEmpty
        {
            return URL(fileURLWithPath: override)
                .appendingPathComponent("trinity_runtime")
        }
        let appSupport = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(
            "Library/Application Support"
        )
        return appSupport
            .appendingPathComponent("Trinity")
            .appendingPathComponent("trinity_runtime")
    }

    static func adaptersRoot() -> URL {
        runtimeRoot().appendingPathComponent("adapters")
    }

    private static func discoveredAdapterNames() -> [String] {
        let adaptersRoot = adaptersRoot()
        guard let children = try? FileManager.default.contentsOfDirectory(
            at: adaptersRoot,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        ) else {
            return builtInAdapters.map(\.adapterName)
        }
        return children.compactMap { url in
            let values = try? url.resourceValues(forKeys: [.isDirectoryKey])
            guard values?.isDirectory == true else {
                return nil
            }
            return url.lastPathComponent
        }
    }
}
