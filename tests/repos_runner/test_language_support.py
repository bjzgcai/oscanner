from pathlib import Path

from repos_runner.services.repo_service.detection import _detect_frameworks_statically
from repos_runner.services.repo_service.parsing import _parse_test_output_with_regex
from repos_runner.services.repo_service.runner import _find_test_files


def test_bundled_docker_image_installs_go_and_rust_toolchains():
    dockerfile = Path("backend/repos_runner/docker/Dockerfile").read_text(encoding="utf-8")

    assert "golang-go" in dockerfile
    assert "cargo" in dockerfile
    assert "rustc" in dockerfile


def test_detects_cpp_cmake_project(tmp_path: Path):
    (tmp_path / "CMakeLists.txt").write_text("enable_testing()\n", encoding="utf-8")

    result = _detect_frameworks_statically(tmp_path)

    assert result == {
        "setup_commands": ["cmake -S . -B build", "cmake --build build"],
        "test_commands": ["ctest --test-dir build --output-on-failure 2>&1 | tee .test_report.txt"],
        "language": "cpp",
    }


def test_detects_cpp_make_project(tmp_path: Path):
    (tmp_path / "Makefile").write_text("test:\n\t./tests\n", encoding="utf-8")

    result = _detect_frameworks_statically(tmp_path)

    assert result == {
        "setup_commands": [],
        "test_commands": ["make test 2>&1 | tee .test_report.txt"],
        "language": "cpp",
    }


def test_detects_cpp_meson_project(tmp_path: Path):
    (tmp_path / "meson.build").write_text("project('demo', 'cpp')\n", encoding="utf-8")

    result = _detect_frameworks_statically(tmp_path)

    assert result == {
        "setup_commands": ["meson setup build"],
        "test_commands": ["meson test -C build --print-errorlogs 2>&1 | tee .test_report.txt"],
        "language": "cpp",
    }


def test_detects_cpp_bazel_project(tmp_path: Path):
    (tmp_path / "BUILD.bazel").write_text("cc_test(name = 'sample_test')\n", encoding="utf-8")

    result = _detect_frameworks_statically(tmp_path)

    assert result == {
        "setup_commands": [],
        "test_commands": ["bazel test //... 2>&1 | tee .test_report.txt"],
        "language": "cpp",
    }


def test_finds_cpp_test_files(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
    (tmp_path / "src" / "service_test.cpp").write_text("TEST(Service, Works) {}\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "integration.cc").write_text("TEST(Integration, Works) {}\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "generated_test.cpp").write_text("TEST(Build, Skip) {}\n", encoding="utf-8")

    assert _find_test_files(tmp_path, "cpp") == [
        "src/service_test.cpp",
        "tests/integration.cc",
    ]


def test_parses_ctest_summary_output():
    output = """
Test project /repo/build
    Start 1: service_test
1/2 Test #1: service_test .....................   Passed    0.01 sec
    Start 2: api_test
2/2 Test #2: api_test .........................***Failed    0.02 sec

50% tests passed, 1 tests failed out of 2
"""

    assert _parse_test_output_with_regex(output) == {"passed": 1, "failed": 1, "total": 2}


def test_parses_googletest_summary_output():
    output = """
[==========] Running 3 tests from 1 test suite.
[  PASSED  ] 2 tests.
[  FAILED  ] 1 test, listed below:
"""

    assert _parse_test_output_with_regex(output) == {"passed": 2, "failed": 1, "total": 3}
