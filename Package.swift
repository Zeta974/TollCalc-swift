// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "TollKit",
    defaultLocalization: "fr",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "TollKit", targets: ["TollKit"]),
    ],
    targets: [
        .target(
            name: "TollKit",
            resources: [.copy("Resources/networks")]
        ),
        .testTarget(
            name: "TollKitTests",
            dependencies: ["TollKit"],
            resources: [.copy("Resources")]
        ),
    ]
)
