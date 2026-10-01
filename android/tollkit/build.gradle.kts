import org.jetbrains.kotlin.gradle.dsl.JvmTarget

// TollKit for Android: the pricing engine as a pure Kotlin/JVM library, so it
// runs unchanged in an Android app and in plain `./gradlew :tollkit:test`.
plugins {
    id("org.jetbrains.kotlin.jvm")
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

// The tariff grids are shared with the Swift package: Tools/build_tariffs.py
// writes them once, to Sources/TollKit/Resources/networks. A classpath can't
// be listed from inside an APK, so an index of the grids is generated next to them.
val networksDir = rootProject.layout.projectDirectory.dir("../Sources/TollKit/Resources")
val generatedResources = layout.buildDirectory.dir("generated/networkIndex")

val generateNetworkIndex by tasks.registering {
    val input = networksDir.dir("networks")
    val output = generatedResources
    inputs.dir(input)
    outputs.dir(output)
    doLast {
        val names = input.asFile.listFiles { f -> f.extension == "json" }!!.map { it.name }.sorted()
        val index = output.get().file("networks/index.txt").asFile
        index.parentFile.mkdirs()
        index.writeText(names.joinToString("\n", postfix = "\n"))
    }
}

sourceSets {
    main {
        resources.srcDir(networksDir)
        resources.srcDir(files(generatedResources).builtBy(generateNetworkIndex))
    }
}

dependencies {
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
    maxHeapSize = "1g"
}
