// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "UsageDock",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "UsageDock", targets: ["UsageDock"])
    ],
    targets: [
        .executableTarget(
            name: "UsageDock",
            path: "Sources/UsageDock",
            exclude: ["Resources"]
        )
    ]
)
