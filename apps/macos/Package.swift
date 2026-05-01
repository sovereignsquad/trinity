// swift-tools-version: 6.1

import PackageDescription

let package = Package(
    name: "Trinity",
    platforms: [
        .macOS(.v15)
    ],
    products: [
        .executable(name: "Trinity", targets: ["TrinityApp"])
    ],
    targets: [
        .executableTarget(
            name: "TrinityApp",
            path: "Sources/TrinityApp"
        )
    ]
)

