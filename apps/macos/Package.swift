// swift-tools-version: 6.1

import PackageDescription

let package = Package(
    name: "trinity-macos",
    platforms: [
        .macOS(.v15)
    ],
    products: [
        .executable(name: "trinity", targets: ["TrinityApp"])
    ],
    targets: [
        .executableTarget(
            name: "TrinityApp",
            path: "Sources/TrinityApp"
        )
    ]
)
