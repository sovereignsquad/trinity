import Foundation
import SwiftUI

enum TrinityAdminProvider: String, CaseIterable, Identifiable {
    case deterministic
    case ollama
    case mistralCLI = "mistral-cli"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .deterministic: "deterministic"
        case .ollama: "ollama"
        case .mistralCLI: "mistral-cli"
        }
    }
}

enum TrinityAdminRole: String, CaseIterable, Identifiable {
    case generator
    case refiner
    case evaluator

    var id: String { rawValue }

    var label: String {
        rawValue.capitalized
    }
}

enum TrinityTrainTransport: String, CaseIterable, Identifiable {
    case api
    case cli

    var id: String { rawValue }
}

struct TrinityAdapterFoundationPolicy: Codable {
    var supportedProviders: [String]
    var preferredLiveProvider: String?
    var releaseGateRoles: [String]

    enum CodingKeys: String, CodingKey {
        case supportedProviders = "supported_providers"
        case preferredLiveProvider = "preferred_live_provider"
        case releaseGateRoles = "release_gate_roles"
    }
}

struct TrinityOptionalSeamsPolicy: Codable {
    var gobiiRequiredForRelease: Bool

    enum CodingKeys: String, CodingKey {
        case gobiiRequiredForRelease = "gobii_required_for_release"
    }
}

struct TrinityTrainPolicy: Codable {
    var defaultTransport: String

    enum CodingKeys: String, CodingKey {
        case defaultTransport = "default_transport"
    }
}

struct TrinityFoundationPolicyDocument: Codable {
    var contractVersion: String
    var train: TrinityTrainPolicy
    var reply: TrinityAdapterFoundationPolicy
    var spot: TrinityAdapterFoundationPolicy
    var optionalSeams: TrinityOptionalSeamsPolicy

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case train
        case reply
        case spot
        case optionalSeams = "optional_seams"
    }

    static let `default` = TrinityFoundationPolicyDocument(
        contractVersion: "trinity_foundation_policy.v1",
        train: TrinityTrainPolicy(defaultTransport: "cli"),
        reply: TrinityAdapterFoundationPolicy(
            supportedProviders: ["deterministic", "mistral-cli"],
            preferredLiveProvider: "mistral-cli",
            releaseGateRoles: ["generator", "refiner", "evaluator"]
        ),
        spot: TrinityAdapterFoundationPolicy(
            supportedProviders: ["deterministic"],
            preferredLiveProvider: nil,
            releaseGateRoles: []
        ),
        optionalSeams: TrinityOptionalSeamsPolicy(gobiiRequiredForRelease: false)
    )
}

struct TrinityRoleRouteDocument: Codable {
    var provider: String
    var model: String
    var temperature: Double
    var keepAlive: String
    var modelID: String?

    enum CodingKeys: String, CodingKey {
        case provider
        case model
        case temperature
        case keepAlive = "keep_alive"
        case modelID = "model_id"
    }
}

struct TrinityAdapterModelConfigDocument: Codable {
    var provider: String
    var ollamaBaseURL: String
    var timeoutSeconds: Double
    var generator: TrinityRoleRouteDocument
    var refiner: TrinityRoleRouteDocument
    var evaluator: TrinityRoleRouteDocument
    var mistralCLIExecutable: String
    var mistralCLIArgs: [String]
    var mistralCLIMode: String
    var mistralCLIModelBinding: String

    enum CodingKeys: String, CodingKey {
        case provider
        case ollamaBaseURL = "ollama_base_url"
        case timeoutSeconds = "timeout_seconds"
        case generator
        case refiner
        case evaluator
        case mistralCLIExecutable = "mistral_cli_executable"
        case mistralCLIArgs = "mistral_cli_args"
        case mistralCLIMode = "mistral_cli_mode"
        case mistralCLIModelBinding = "mistral_cli_model_binding"
    }

    static func `default`(adapterName: String) -> TrinityAdapterModelConfigDocument {
        let isReply = adapterName == "reply"
        let provider = isReply ? "mistral-cli" : "deterministic"
        return TrinityAdapterModelConfigDocument(
            provider: provider,
            ollamaBaseURL: "http://127.0.0.1:11434",
            timeoutSeconds: 45.0,
            generator: TrinityRoleRouteDocument(
                provider: provider,
                model: isReply ? "mistral-small-latest" : "granite4:350m",
                temperature: 0.25,
                keepAlive: "10m",
                modelID: nil
            ),
            refiner: TrinityRoleRouteDocument(
                provider: provider,
                model: isReply ? "mistral-small-latest" : "mistral:latest",
                temperature: 0.35,
                keepAlive: "10m",
                modelID: nil
            ),
            evaluator: TrinityRoleRouteDocument(
                provider: provider,
                model: isReply ? "mistral-medium-latest" : "qwen2.5:7b",
                temperature: 0.1,
                keepAlive: "10m",
                modelID: nil
            ),
            mistralCLIExecutable: "vibe",
            mistralCLIArgs: [],
            mistralCLIMode: "vibe",
            mistralCLIModelBinding: "advisory"
        )
    }
}

@MainActor
final class TrinityAdminSettingsStore: ObservableObject {
    @Published var foundationPolicy = TrinityFoundationPolicyDocument.default
    @Published var replyConfig = TrinityAdapterModelConfigDocument.default(adapterName: "reply")
    @Published var spotConfig = TrinityAdapterModelConfigDocument.default(adapterName: "spot")
    @Published var statusMessage = "Ready"
    @Published var lastSavedAt: Date?

    let foundationPolicyPath: URL
    let replyConfigPath: URL
    let spotConfigPath: URL

    init() {
        self.foundationPolicyPath = Self.foundationPolicyPathURL()
        self.replyConfigPath = Self.adapterConfigPath(adapterName: "reply")
        self.spotConfigPath = Self.adapterConfigPath(adapterName: "spot")
        reload()
    }

    func reload() {
        do {
            foundationPolicy = try loadDocument(
                from: foundationPolicyPath,
                fallback: .default
            )
            replyConfig = try loadDocument(
                from: replyConfigPath,
                fallback: .default(adapterName: "reply")
            )
            spotConfig = try loadDocument(
                from: spotConfigPath,
                fallback: .default(adapterName: "spot")
            )
            statusMessage = "Loaded machine-local settings."
        } catch {
            statusMessage = "Load failed: \(error.localizedDescription)"
        }
    }

    func saveAll() {
        do {
            foundationPolicy = normalized(policy: foundationPolicy)
            replyConfig = normalized(config: replyConfig)
            spotConfig = normalized(config: spotConfig)
            try saveDocument(foundationPolicy, to: foundationPolicyPath)
            try saveDocument(replyConfig, to: replyConfigPath)
            try saveDocument(spotConfig, to: spotConfigPath)
            lastSavedAt = Date()
            statusMessage = "Saved foundation policy and adapter config."
        } catch {
            statusMessage = "Save failed: \(error.localizedDescription)"
        }
    }

    func toggleSupportedProvider(
        adapterName: String,
        provider: TrinityAdminProvider,
        enabled: Bool
    ) {
        var target = adapterName == "reply" ? foundationPolicy.reply : foundationPolicy.spot
        var providers = Set(target.supportedProviders)
        if enabled {
            providers.insert(provider.rawValue)
        } else {
            providers.remove(provider.rawValue)
            if target.preferredLiveProvider == provider.rawValue {
                target.preferredLiveProvider = nil
            }
        }
        target.supportedProviders = providers.sorted()
        applyAdapterPolicy(target, adapterName: adapterName)
    }

    func setReleaseGateRole(
        adapterName: String,
        role: TrinityAdminRole,
        enabled: Bool
    ) {
        var target = adapterName == "reply" ? foundationPolicy.reply : foundationPolicy.spot
        var roles = Set(target.releaseGateRoles)
        if enabled {
            roles.insert(role.rawValue)
        } else {
            roles.remove(role.rawValue)
        }
        target.releaseGateRoles = roles.sorted()
        applyAdapterPolicy(target, adapterName: adapterName)
    }

    func bindingForRoleModel(
        adapterName: String,
        role: TrinityAdminRole
    ) -> Binding<String> {
        Binding(
            get: {
                switch (adapterName, role) {
                case ("reply", .generator): self.replyConfig.generator.model
                case ("reply", .refiner): self.replyConfig.refiner.model
                case ("reply", .evaluator): self.replyConfig.evaluator.model
                case ("spot", .generator): self.spotConfig.generator.model
                case ("spot", .refiner): self.spotConfig.refiner.model
                case ("spot", .evaluator): self.spotConfig.evaluator.model
                default: ""
                }
            },
            set: { value in
                switch (adapterName, role) {
                case ("reply", .generator): self.replyConfig.generator.model = value
                case ("reply", .refiner): self.replyConfig.refiner.model = value
                case ("reply", .evaluator): self.replyConfig.evaluator.model = value
                case ("spot", .generator): self.spotConfig.generator.model = value
                case ("spot", .refiner): self.spotConfig.refiner.model = value
                case ("spot", .evaluator): self.spotConfig.evaluator.model = value
                default: break
                }
            }
        )
    }

    private func applyAdapterPolicy(
        _ updatedPolicy: TrinityAdapterFoundationPolicy,
        adapterName: String
    ) {
        if adapterName == "reply" {
            foundationPolicy.reply = updatedPolicy
        } else {
            foundationPolicy.spot = updatedPolicy
        }
    }

    private func normalized(policy: TrinityFoundationPolicyDocument) -> TrinityFoundationPolicyDocument {
        var value = policy
        value.reply = normalized(adapterPolicy: value.reply)
        value.spot = normalized(adapterPolicy: value.spot)
        return value
    }

    private func normalized(adapterPolicy: TrinityAdapterFoundationPolicy) -> TrinityAdapterFoundationPolicy {
        var value = adapterPolicy
        value.supportedProviders = Array(Set(value.supportedProviders)).sorted()
        value.releaseGateRoles = Array(Set(value.releaseGateRoles)).sorted()
        if let preferred = value.preferredLiveProvider, !preferred.isEmpty {
            if !value.supportedProviders.contains(preferred) {
                value.supportedProviders.append(preferred)
                value.supportedProviders.sort()
            }
        } else {
            value.preferredLiveProvider = nil
        }
        return value
    }

    private func normalized(config: TrinityAdapterModelConfigDocument) -> TrinityAdapterModelConfigDocument {
        var value = config
        value.generator.provider = value.provider
        value.refiner.provider = value.provider
        value.evaluator.provider = value.provider
        value.mistralCLIArgs = value.mistralCLIArgs.filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        return value
    }

    private func loadDocument<T: Decodable>(
        from url: URL,
        fallback: T
    ) throws -> T {
        guard FileManager.default.fileExists(atPath: url.path) else {
            return fallback
        }
        let data = try Data(contentsOf: url)
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func saveDocument<T: Encodable>(_ document: T, to url: URL) throws {
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(document)
        try data.write(to: url, options: .atomic)
    }

    private static func foundationPolicyPathURL() -> URL {
        runtimeRoot().appendingPathComponent("foundation_policy.json")
    }

    private static func adapterConfigPath(adapterName: String) -> URL {
        let root = runtimeRoot().appendingPathComponent("adapters")
        let namespacedRoot = root.appendingPathComponent(adapterName)
        if adapterName == "reply" {
            let legacy = appSupportRoot().appendingPathComponent("reply_runtime")
            if FileManager.default.fileExists(atPath: legacy.path),
               !FileManager.default.fileExists(atPath: namespacedRoot.path) {
                return legacy.appendingPathComponent("model_config.json")
            }
        }
        return namespacedRoot.appendingPathComponent("model_config.json")
    }

    private static func runtimeRoot() -> URL {
        appSupportRoot().appendingPathComponent("trinity_runtime")
    }

    private static func appSupportRoot() -> URL {
        if let override = ProcessInfo.processInfo.environment["TRINITY_APP_SUPPORT_DIR"],
           !override.isEmpty
        {
            return URL(fileURLWithPath: override)
        }
        let appSupport = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(
            "Library/Application Support"
        )
        return appSupport.appendingPathComponent("Trinity")
    }
}

struct TrinityAdminSettingsView: View {
    @StateObject private var store = TrinityAdminSettingsStore()
    private let showsOwnScrollView: Bool

    init(showsOwnScrollView: Bool = true) {
        self.showsOwnScrollView = showsOwnScrollView
    }

    var body: some View {
        Group {
            if showsOwnScrollView {
                ScrollView {
                    content
                }
            } else {
                content
            }
        }
        .frame(minWidth: 760, minHeight: 720)
        .background(TrinityPalette.canvas.opacity(0.45))
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 18) {
            header
            foundationPanel
            adapterPanel(
                title: "Reply Runtime",
                subtitle: "Active live adapter config and preferred live-path policy.",
                adapterName: "reply",
                config: $store.replyConfig,
                policy: $store.foundationPolicy.reply
            )
            adapterPanel(
                title: "Spot Runtime",
                subtitle: "Bounded second adapter config and supported-provider policy.",
                adapterName: "spot",
                config: $store.spotConfig,
                policy: $store.foundationPolicy.spot
            )
        }
        .padding(24)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Admin Settings")
                        .font(.title.weight(.semibold))
                        .foregroundStyle(TrinityPalette.textPrimary)
                    Text("Machine-local foundation policy and active adapter model routing.")
                        .foregroundStyle(TrinityPalette.textSecondary)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 6) {
                    TrinityStatusPill(label: store.statusMessage, color: TrinityPalette.info)
                    if let lastSavedAt = store.lastSavedAt {
                        Text(lastSavedAt.formatted(date: .omitted, time: .standard))
                            .font(.caption)
                            .foregroundStyle(TrinityPalette.textSecondary)
                    }
                }
            }
            HStack(spacing: 10) {
                Button("Reload") {
                    store.reload()
                }
                Button("Save All") {
                    store.saveAll()
                }
                .buttonStyle(.borderedProminent)
                Spacer()
                pathBadge(label: "Foundation", path: store.foundationPolicyPath.path)
                pathBadge(label: "Reply", path: store.replyConfigPath.path)
                pathBadge(label: "Spot", path: store.spotConfigPath.path)
            }
        }
        .trinityPanel()
    }

    private var foundationPanel: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Foundation Policy")
                .font(.title3.weight(.semibold))
            Text("This is the operator baseline used by the CLI release gates and preflight checks.")
                .foregroundStyle(TrinityPalette.textSecondary)
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Train Default Transport")
                        .font(.headline)
                    Picker(
                        "Train Default Transport",
                        selection: $store.foundationPolicy.train.defaultTransport
                    ) {
                        ForEach(TrinityTrainTransport.allCases) { transport in
                            Text(transport.rawValue).tag(transport.rawValue)
                        }
                    }
                    .pickerStyle(.segmented)
                }
                VStack(alignment: .leading, spacing: 8) {
                    Text("Optional Seams")
                        .font(.headline)
                    Toggle(
                        "Require Gobii in foundation release checks",
                        isOn: $store.foundationPolicy.optionalSeams.gobiiRequiredForRelease
                    )
                    .toggleStyle(.switch)
                }
            }
        }
        .trinityPanel()
    }

    private func adapterPanel(
        title: String,
        subtitle: String,
        adapterName: String,
        config: Binding<TrinityAdapterModelConfigDocument>,
        policy: Binding<TrinityAdapterFoundationPolicy>
    ) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(title)
                .font(.title3.weight(.semibold))
            Text(subtitle)
                .foregroundStyle(TrinityPalette.textSecondary)
            HStack(alignment: .top, spacing: 20) {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Active Runtime Config")
                        .font(.headline)
                    Picker("Provider", selection: config.provider) {
                        ForEach(TrinityAdminProvider.allCases) { provider in
                            Text(provider.label).tag(provider.rawValue)
                        }
                    }
                    .pickerStyle(.segmented)
                    configField(
                        label: "Generator Model",
                        text: store.bindingForRoleModel(adapterName: adapterName, role: .generator)
                    )
                    configField(
                        label: "Refiner Model",
                        text: store.bindingForRoleModel(adapterName: adapterName, role: .refiner)
                    )
                    configField(
                        label: "Evaluator Model",
                        text: store.bindingForRoleModel(adapterName: adapterName, role: .evaluator)
                    )
                    configField(label: "Ollama Base URL", text: config.ollamaBaseURL)
                    configField(label: "Mistral Executable", text: config.mistralCLIExecutable)
                    configField(label: "Mistral Args", text: Binding(
                        get: { config.wrappedValue.mistralCLIArgs.joined(separator: " ") },
                        set: { config.wrappedValue.mistralCLIArgs = $0.split(separator: " ").map(String.init) }
                    ))
                }
                Divider()
                VStack(alignment: .leading, spacing: 12) {
                    Text("Foundation Gate Policy")
                        .font(.headline)
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Supported Providers")
                            .font(.subheadline.weight(.semibold))
                        ForEach(TrinityAdminProvider.allCases) { providerOption in
                            Toggle(
                                providerOption.label,
                                isOn: Binding(
                                    get: {
                                        policy.wrappedValue.supportedProviders.contains(
                                            providerOption.rawValue
                                        )
                                    },
                                    set: { enabled in
                                        store.toggleSupportedProvider(
                                            adapterName: adapterName,
                                            provider: providerOption,
                                            enabled: enabled
                                        )
                                    }
                                )
                            )
                        }
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Preferred Live Provider")
                            .font(.subheadline.weight(.semibold))
                        Picker("Preferred Live Provider", selection: Binding(
                            get: { policy.wrappedValue.preferredLiveProvider ?? "" },
                            set: { value in
                                policy.wrappedValue.preferredLiveProvider = value.isEmpty ? nil : value
                            }
                        )) {
                            Text("None").tag("")
                            ForEach(TrinityAdminProvider.allCases) { providerOption in
                                Text(providerOption.label).tag(providerOption.rawValue)
                            }
                        }
                        .pickerStyle(.menu)
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Release-Gate Smoke Roles")
                            .font(.subheadline.weight(.semibold))
                        ForEach(TrinityAdminRole.allCases) { role in
                            Toggle(
                                role.label,
                                isOn: Binding(
                                    get: {
                                        policy.wrappedValue.releaseGateRoles.contains(role.rawValue)
                                    },
                                    set: { enabled in
                                        store.setReleaseGateRole(
                                            adapterName: adapterName,
                                            role: role,
                                            enabled: enabled
                                        )
                                    }
                                )
                            )
                        }
                    }
                }
                .frame(maxWidth: 280)
            }
        }
        .trinityPanel()
    }

    private func configField(label: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.subheadline.weight(.semibold))
            TextField(label, text: text)
                .textFieldStyle(.roundedBorder)
        }
    }

    private func pathBadge(label: String, path: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(TrinityPalette.textPrimary)
            Text(path)
                .font(.caption2)
                .foregroundStyle(TrinityPalette.textSecondary)
                .lineLimit(2)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(TrinityPalette.panelAlt.opacity(0.7))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}
