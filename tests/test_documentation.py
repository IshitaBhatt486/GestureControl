import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "docs" / "USER_GUIDE.md",
    ROOT / "docs" / "DEVELOPER_GUIDE.md",
    ROOT / "docs" / "ARCHITECTURE.md",
    ROOT / "docs" / "BENCHMARK_REPORT.md",
    ROOT / "docs" / "TROUBLESHOOTING.md",
)


def test_complete_documentation_set_exists_and_is_substantial():
    for document in DOCUMENTS:
        assert document.is_file(), document
        assert len(document.read_text(encoding="utf-8")) > 1_000, document


def test_all_local_markdown_images_exist():
    for document in DOCUMENTS:
        contents = document.read_text(encoding="utf-8")
        for target in re.findall(r"!\[[^]]*]\(([^)]+)\)", contents):
            if "://" not in target:
                assert (document.parent / target).resolve().is_file(), (document, target)


def test_architecture_and_benchmark_docs_contain_diagrams():
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    benchmark = (ROOT / "docs" / "BENCHMARK_REPORT.md").read_text(encoding="utf-8")
    assert architecture.count("```mermaid") >= 4
    assert "```mermaid" in benchmark
