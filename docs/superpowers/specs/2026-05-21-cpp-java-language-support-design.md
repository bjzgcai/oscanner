# C/C++ and Java Language Support Design

## Goal

Oscanner should support C/C++ and Java across repository test execution and evaluation context, and the courses app should clearly advertise the supported language set.

## Scope

- Add C/C++ runner detection, test-file discovery, and common test-output parsing.
- Keep existing Java runner support, and add Java evaluation-context selection for build manifests and imported local classes.
- Add C/C++ evaluation-context selection for build manifests and local headers included from changed files.
- Update courses backend README and homepage copy to highlight Python, JavaScript/TypeScript, Go, Rust, Java, and C/C++ support.

## Runner Behavior

The repos runner will statically detect C/C++ projects from common build files:

- `CMakeLists.txt`: configure/build with CMake and run `ctest`.
- `Makefile`: run `make test`.
- `meson.build`: configure/build with Meson and run `meson test`.
- `BUILD`, `BUILD.bazel`, or `WORKSPACE`: run `bazel test //...`.

C/C++ test discovery will recognize `.c`, `.cc`, `.cpp`, `.cxx`, `.h`, `.hpp`, `.hh`, and `.hxx` files with common test names or files under `test` / `tests` directories. Existing Java Maven/Gradle commands remain unchanged.

## Evaluation Context

Both bundled plugins will select relevant background context for C/C++ and Java commits:

- C/C++ root manifests: `CMakeLists.txt`, `Makefile`, `meson.build`, `conanfile.txt`, `conanfile.py`, `vcpkg.json`.
- Java root manifests: `pom.xml`, `build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts`, `gradlew`.
- C/C++ local includes from changed source/header files.
- Java local imports and same-package classes when matching files exist in the repo snapshot.

Repository snapshot files stay background-only evidence, preserving the existing scoring contract.

## Courses Visibility

The courses backend README and `/` homepage should explicitly state the supported language set so teachers and students know C/C++ and Java submissions are first-class runner/evaluation targets.

## Tests

- Unit tests for C/C++ static framework detection and C/C++ test-file discovery.
- Unit tests for `ctest` and GoogleTest-style regex parsing.
- Plugin snapshot tests for C/C++ include context and Java build/import context.
- Frontend build/lint verification for the homepage copy change.
