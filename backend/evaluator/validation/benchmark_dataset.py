"""
Curated benchmark dataset of test repositories for validation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum
from pathlib import Path


class SkillLevel(Enum):
    """Expected skill level categories"""
    NOVICE = "novice"           # 0-1 year
    INTERMEDIATE = "intermediate"  # 2-3 years
    SENIOR = "senior"           # 5+ years
    ARCHITECT = "architect"     # 8+ years, system design
    EXPERT = "expert"           # 10+ years, thought leader


class DimensionStrength(Enum):
    """Dimension-specific strength indicators"""
    AI_MODEL = "ai_model"
    AI_NATIVE = "ai_native"
    CLOUD_NATIVE = "cloud_native"
    OPEN_SOURCE = "open_source"
    INTELLIGENT_DEV = "intelligent_dev"
    LEADERSHIP = "leadership"


@dataclass
class TestRepository:
    """
    A test repository with expected evaluation characteristics
    """
    # Basic info
    platform: str  # "github" or "gitee"
    owner: str
    repo: str
    author: str  # Author to evaluate in this repo

    # Expected characteristics
    skill_level: Optional[SkillLevel] = None
    expected_score_range: Optional[tuple[int, int]] = None  # (min, max)

    # Dimension-specific expectations
    strong_dimensions: List[DimensionStrength] = field(default_factory=list)
    weak_dimensions: List[DimensionStrength] = field(default_factory=list)

    # Expected scores per dimension (if known)
    expected_dimension_scores: Dict[str, tuple[int, int]] = field(default_factory=dict)

    # Metadata
    category: str = "general"  # Category of this test
    description: str = ""
    public_reputation: Optional[str] = None  # Known public reputation

    # Temporal tracking (for evolution tests)
    time_period: Optional[str] = None  # e.g., "2009-2010", "2024-2025"
    temporal_group: Optional[str] = None  # Group ID for same dev over time

    # Validation flags
    is_ground_truth: bool = False  # Human-verified
    is_edge_case: bool = False

    @property
    def repo_url(self) -> str:
        """Get full repository URL"""
        if self.platform == "github":
            return f"https://github.com/{self.owner}/{self.repo}"
        elif self.platform == "gitee":
            return f"https://gitee.com/{self.owner}/{self.repo}"
        else:
            return f"{self.platform}:{self.owner}/{self.repo}"

    @property
    def identifier(self) -> str:
        """Unique identifier for this test"""
        return f"{self.platform}/{self.owner}/{self.repo}/{self.author}"

    def __repr__(self) -> str:
        return f"TestRepo({self.identifier}, level={self.skill_level}, category={self.category})"


class BenchmarkDataset:
    """
    Curated collection of test repositories organized by category
    """

    def __init__(self):
        self.repos: List[TestRepository] = []
        self._init_dataset()

    def _init_dataset(self):
        """Initialize the curated dataset"""

        # ========== Category A: Ground Truth (Controlled Repos) ==========
        self.repos.extend([
            TestRepository(
                platform="github",
                owner="bjzgcai",
                repo="eval_test_junior",
                author="bjzgcai",
                skill_level=SkillLevel.NOVICE,
                expected_score_range=(30, 50),
                category="ground_truth",
                description="Manually constructed junior-level repository",
                is_ground_truth=True
            ),
            TestRepository(
                platform="github",
                owner="bjzgcai",
                repo="eval_test_senior",
                author="bjzgcai",
                skill_level=SkillLevel.SENIOR,
                expected_score_range=(70, 85),
                category="ground_truth",
                description="Manually constructed senior-level repository",
                is_ground_truth=True
            ),
        ])

        # ========== Category B: Famous Developers (Public Reputation) ==========
        self.repos.extend([
            # Linus Torvalds - Linux Kernel
            TestRepository(
                platform="github",
                owner="torvalds",
                repo="linux",
                author="torvalds",
                skill_level=SkillLevel.EXPERT,
                expected_score_range=(90, 98),
                strong_dimensions=[
                    DimensionStrength.LEADERSHIP,
                    DimensionStrength.OPEN_SOURCE,
                    DimensionStrength.CLOUD_NATIVE
                ],
                category="famous_developer",
                description="Creator of Linux kernel and Git",
                public_reputation="One of most influential developers in history"
            ),

            # Evan You - Vue.js
            TestRepository(
                platform="github",
                owner="yyx990803",
                repo="vue",
                author="yyx990803",
                skill_level=SkillLevel.EXPERT,
                expected_score_range=(88, 96),
                strong_dimensions=[
                    DimensionStrength.OPEN_SOURCE,
                    DimensionStrength.AI_NATIVE,
                    DimensionStrength.INTELLIGENT_DEV
                ],
                category="famous_developer",
                description="Creator of Vue.js framework",
                public_reputation="Popular framework creator, strong community leadership"
            ),

            # Dan Abramov - Redux & React
            TestRepository(
                platform="github",
                owner="gaearon",
                repo="redux",
                author="gaearon",
                skill_level=SkillLevel.EXPERT,
                expected_score_range=(88, 95),
                strong_dimensions=[
                    DimensionStrength.OPEN_SOURCE,
                    DimensionStrength.INTELLIGENT_DEV,
                    DimensionStrength.LEADERSHIP
                ],
                category="famous_developer",
                description="Co-creator of Redux, React core team",
                public_reputation="Influential educator and OSS contributor"
            ),

            # TJ Holowaychuk - Express.js & many Node tools
            TestRepository(
                platform="github",
                owner="tj",
                repo="commander.js",
                author="tj",
                skill_level=SkillLevel.EXPERT,
                expected_score_range=(85, 93),
                strong_dimensions=[
                    DimensionStrength.OPEN_SOURCE,
                    DimensionStrength.INTELLIGENT_DEV
                ],
                category="famous_developer",
                description="Prolific Node.js ecosystem contributor",
                public_reputation="Created 100+ popular npm packages"
            ),

            # Sindre Sorhus - Prolific OSS contributor
            TestRepository(
                platform="github",
                owner="sindresorhus",
                repo="got",
                author="sindresorhus",
                skill_level=SkillLevel.EXPERT,
                expected_score_range=(85, 92),
                strong_dimensions=[
                    DimensionStrength.OPEN_SOURCE,
                    DimensionStrength.INTELLIGENT_DEV
                ],
                category="famous_developer",
                description="1000+ npm packages, GitHub star ranking",
                public_reputation="Most starred developer on GitHub"
            ),
        ])

        # ========== Category C: Dimension Specialists ==========

        # AI Model Specialists
        self.repos.extend([
            TestRepository(
                platform="github",
                owner="huggingface",
                repo="transformers",
                author="sgugger",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.AI_MODEL, DimensionStrength.OPEN_SOURCE],
                expected_dimension_scores={
                    "ai_model": (85, 95),
                },
                category="dimension_specialist_ai",
                description="Hugging Face Transformers core contributor",
                public_reputation="AI/ML framework expert"
            ),
            TestRepository(
                platform="github",
                owner="langchain-ai",
                repo="langchain",
                author="hwchase17",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.AI_MODEL, DimensionStrength.AI_NATIVE],
                expected_dimension_scores={
                    "ai_model": (85, 95),
                    "ai_native": (80, 92),
                },
                category="dimension_specialist_ai",
                description="LangChain creator - LLM application framework",
                public_reputation="Pioneer in LLM app architecture"
            ),
            TestRepository(
                platform="github",
                owner="karpathy",
                repo="nanoGPT",
                author="karpathy",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.AI_MODEL, DimensionStrength.INTELLIGENT_DEV],
                expected_dimension_scores={
                    "ai_model": (90, 98),
                },
                category="dimension_specialist_ai",
                description="Andrej Karpathy - Tesla AI director, educator",
                public_reputation="AI expert, clear educator"
            ),
        ])

        # Cloud Native Specialists
        self.repos.extend([
            TestRepository(
                platform="github",
                owner="kubernetes",
                repo="kubernetes",
                author="kelseyhightower",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.CLOUD_NATIVE, DimensionStrength.LEADERSHIP],
                expected_dimension_scores={
                    "cloud_native": (88, 96),
                },
                category="dimension_specialist_cloud",
                description="Kubernetes contributor, cloud native advocate",
                public_reputation="Google Cloud advocate, K8s expert"
            ),
            TestRepository(
                platform="github",
                owner="kubernetes",
                repo="kubernetes",
                author="brendandburns",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.CLOUD_NATIVE, DimensionStrength.LEADERSHIP],
                expected_dimension_scores={
                    "cloud_native": (85, 95),
                },
                category="dimension_specialist_cloud",
                description="Kubernetes co-founder",
                public_reputation="Microsoft VP, K8s co-creator"
            ),
            TestRepository(
                platform="github",
                owner="istio",
                repo="istio",
                author="howardjohn",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.CLOUD_NATIVE],
                expected_dimension_scores={
                    "cloud_native": (82, 92),
                },
                category="dimension_specialist_cloud",
                description="Istio service mesh core contributor",
                public_reputation="Service mesh expert"
            ),
        ])

        # Open Source Collaboration Specialists
        self.repos.extend([
            TestRepository(
                platform="github",
                owner="microsoft",
                repo="vscode",
                author="bpasero",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.OPEN_SOURCE, DimensionStrength.LEADERSHIP],
                expected_dimension_scores={
                    "open_source": (85, 94),
                },
                category="dimension_specialist_opensource",
                description="VS Code core team, extensive collaboration",
                public_reputation="VS Code maintainer"
            ),
            TestRepository(
                platform="github",
                owner="nodejs",
                repo="node",
                author="jasnell",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.OPEN_SOURCE, DimensionStrength.LEADERSHIP],
                expected_dimension_scores={
                    "open_source": (82, 92),
                },
                category="dimension_specialist_opensource",
                description="Node.js core contributor and TSC member",
                public_reputation="Node.js Technical Steering Committee"
            ),
            TestRepository(
                platform="github",
                owner="rust-lang",
                repo="rust",
                author="nikomatsakis",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.OPEN_SOURCE, DimensionStrength.LEADERSHIP],
                expected_dimension_scores={
                    "open_source": (85, 95),
                },
                category="dimension_specialist_opensource",
                description="Rust language core team member",
                public_reputation="Rust core team, language design"
            ),
        ])

        # Intelligent Development Specialists
        self.repos.extend([
            TestRepository(
                platform="github",
                owner="vercel",
                repo="next.js",
                author="timneutkens",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.INTELLIGENT_DEV, DimensionStrength.AI_NATIVE],
                expected_dimension_scores={
                    "intelligent_dev": (85, 94),
                },
                category="dimension_specialist_intelligent",
                description="Next.js co-creator, modern tooling",
                public_reputation="React framework innovation"
            ),
            TestRepository(
                platform="github",
                owner="vitejs",
                repo="vite",
                author="yyx990803",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.INTELLIGENT_DEV, DimensionStrength.AI_NATIVE],
                expected_dimension_scores={
                    "intelligent_dev": (88, 96),
                },
                category="dimension_specialist_intelligent",
                description="Vite build tool creator",
                public_reputation="Performance-focused tooling expert"
            ),
            TestRepository(
                platform="github",
                owner="evanw",
                repo="esbuild",
                author="evanw",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.INTELLIGENT_DEV],
                expected_dimension_scores={
                    "intelligent_dev": (90, 97),
                },
                category="dimension_specialist_intelligent",
                description="esbuild creator - extremely fast bundler",
                public_reputation="Performance engineering expert"
            ),
        ])

        # Leadership Specialists
        self.repos.extend([
            TestRepository(
                platform="github",
                owner="facebook",
                repo="react",
                author="sebmarkbage",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.LEADERSHIP, DimensionStrength.AI_NATIVE],
                expected_dimension_scores={
                    "leadership": (85, 95),
                },
                category="dimension_specialist_leadership",
                description="React core team, architectural decisions",
                public_reputation="React architect"
            ),
            TestRepository(
                platform="github",
                owner="golang",
                repo="go",
                author="griesemer",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.LEADERSHIP],
                expected_dimension_scores={
                    "leadership": (88, 96),
                },
                category="dimension_specialist_leadership",
                description="Go language core team",
                public_reputation="Go language designer"
            ),
        ])

        # ========== Category D: Rising Stars (Mid-level to Senior) ==========
        self.repos.extend([
            TestRepository(
                platform="github",
                owner="vercel",
                repo="swr",
                author="shuding",
                skill_level=SkillLevel.SENIOR,
                expected_score_range=(75, 88),
                strong_dimensions=[DimensionStrength.INTELLIGENT_DEV, DimensionStrength.OPEN_SOURCE],
                category="rising_star",
                description="SWR creator, Vercel engineer",
                public_reputation="Young but highly productive"
            ),
            TestRepository(
                platform="github",
                owner="antfu",
                repo="vite",
                author="antfu",
                skill_level=SkillLevel.SENIOR,
                expected_score_range=(78, 90),
                strong_dimensions=[DimensionStrength.OPEN_SOURCE, DimensionStrength.INTELLIGENT_DEV],
                category="rising_star",
                description="Vue core team, prolific tool creator",
                public_reputation="Rising open source contributor"
            ),
            TestRepository(
                platform="github",
                owner="shadcn",
                repo="ui",
                author="shadcn",
                skill_level=SkillLevel.SENIOR,
                expected_score_range=(75, 87),
                strong_dimensions=[DimensionStrength.INTELLIGENT_DEV, DimensionStrength.OPEN_SOURCE],
                category="rising_star",
                description="shadcn/ui creator - component library",
                public_reputation="Viral UI library creator"
            ),
        ])

        # ========== Category E: Temporal Evolution Tests ==========
        self.repos.extend([
            # Sebastian Markbage - Early career
            TestRepository(
                platform="github",
                owner="sebmarkbage",
                repo="calyptus.mvc",
                author="sebmarkbage",
                skill_level=SkillLevel.INTERMEDIATE,
                expected_score_range=(55, 70),
                time_period="2009-2010",
                temporal_group="sebmarkbage",
                category="temporal_evolution",
                description="Early work by Sebastian Markbage"
            ),
            # Sebastian Markbage - Current (React core)
            TestRepository(
                platform="github",
                owner="facebook",
                repo="react",
                author="sebmarkbage",
                skill_level=SkillLevel.EXPERT,
                expected_score_range=(88, 96),
                time_period="2020-2025",
                temporal_group="sebmarkbage",
                category="temporal_evolution",
                description="Current work on React"
            ),
        ])

        # ========== Category F: Edge Cases & Volume Tests ==========
        self.repos.extend([
            # Very small repo (few commits)
            TestRepository(
                platform="github",
                owner="torvalds",
                repo="uemacs",
                author="torvalds",
                skill_level=SkillLevel.EXPERT,
                category="edge_case_small",
                description="Small utility by Linus (edge case: few commits)",
                is_edge_case=True
            ),

            # Documentation-heavy repo
            TestRepository(
                platform="github",
                owner="getify",
                repo="You-Dont-Know-JS",
                author="getify",
                skill_level=SkillLevel.SENIOR,
                expected_score_range=(65, 80),
                weak_dimensions=[DimensionStrength.CLOUD_NATIVE],
                strong_dimensions=[DimensionStrength.OPEN_SOURCE, DimensionStrength.LEADERSHIP],
                category="edge_case_docs",
                description="Educational book repo (mostly docs)",
                is_edge_case=True
            ),

            # Solo developer
            TestRepository(
                platform="github",
                owner="jashkenas",
                repo="underscore",
                author="jashkenas",
                skill_level=SkillLevel.EXPERT,
                expected_score_range=(80, 90),
                weak_dimensions=[DimensionStrength.OPEN_SOURCE],  # Mostly solo
                category="edge_case_solo",
                description="Underscore.js - primarily single author",
                is_edge_case=True
            ),
        ])

        # ========== Category G: Corporate/Team Repos ==========
        self.repos.extend([
            TestRepository(
                platform="github",
                owner="tensorflow",
                repo="tensorflow",
                author="martinwicke",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.AI_MODEL, DimensionStrength.CLOUD_NATIVE],
                expected_dimension_scores={
                    "ai_model": (85, 94),
                },
                category="corporate_team",
                description="TensorFlow core contributor in large team"
            ),
            TestRepository(
                platform="github",
                owner="microsoft",
                repo="TypeScript",
                author="ahejlsberg",
                skill_level=SkillLevel.EXPERT,
                strong_dimensions=[DimensionStrength.LEADERSHIP, DimensionStrength.INTELLIGENT_DEV],
                expected_dimension_scores={
                    "leadership": (90, 98),
                },
                category="corporate_team",
                description="TypeScript creator (Anders Hejlsberg)"
            ),
        ])

        # ========== Category H: Domain Specialists ==========
        self.repos.extend([
            # Security specialist
            TestRepository(
                platform="github",
                owner="sqlmapproject",
                repo="sqlmap",
                author="stamparm",
                skill_level=SkillLevel.EXPERT,
                expected_score_range=(80, 90),
                strong_dimensions=[DimensionStrength.INTELLIGENT_DEV],
                category="domain_security",
                description="Security tool creator (SQLMap)"
            ),

            # Data visualization specialist
            TestRepository(
                platform="github",
                owner="mbostock",
                repo="d3",
                author="mbostock",
                skill_level=SkillLevel.EXPERT,
                expected_score_range=(85, 94),
                strong_dimensions=[DimensionStrength.INTELLIGENT_DEV, DimensionStrength.OPEN_SOURCE],
                category="domain_visualization",
                description="D3.js creator - visualization expert"
            ),

            # Systems programming specialist
            TestRepository(
                platform="github",
                owner="antirez",
                repo="redis",
                author="antirez",
                skill_level=SkillLevel.EXPERT,
                expected_score_range=(88, 95),
                strong_dimensions=[DimensionStrength.CLOUD_NATIVE, DimensionStrength.LEADERSHIP],
                category="domain_systems",
                description="Redis creator - systems programming"
            ),
        ])

        # ========== Category I: International Developers ==========
        self.repos.extend([
            # Chinese developers
            TestRepository(
                platform="gitee",
                owner="dromara",
                repo="hutool",
                author="looly",
                skill_level=SkillLevel.SENIOR,
                expected_score_range=(75, 88),
                strong_dimensions=[DimensionStrength.OPEN_SOURCE],
                category="international_chinese",
                description="Hutool Java utility library creator"
            ),
        ])

        # ========== Category J: Comparison Pairs (Known Ordering) ==========
        # These are used to test relative rankings
        self.repos.extend([
            # Pair 1: Framework creators (should be close)
            TestRepository(
                platform="github",
                owner="yyx990803",
                repo="vue",
                author="yyx990803",
                category="comparison_pair_frameworks",
                description="Vue creator for comparison"
            ),
            TestRepository(
                platform="github",
                owner="facebook",
                repo="react",
                author="gaearon",
                category="comparison_pair_frameworks",
                description="React team for comparison"
            ),

            # Pair 2: Build tool creators (should be close)
            TestRepository(
                platform="github",
                owner="vitejs",
                repo="vite",
                author="yyx990803",
                category="comparison_pair_build",
                description="Vite creator for comparison"
            ),
            TestRepository(
                platform="github",
                owner="evanw",
                repo="esbuild",
                author="evanw",
                category="comparison_pair_build",
                description="esbuild creator for comparison"
            ),
        ])

    def get_all(self) -> List[TestRepository]:
        """Get all test repositories"""
        return self.repos

    def get_by_category(self, category: str) -> List[TestRepository]:
        """Get repositories by category"""
        return [r for r in self.repos if r.category == category]

    def get_ground_truth(self) -> List[TestRepository]:
        """Get only ground truth (manually verified) repositories"""
        return [r for r in self.repos if r.is_ground_truth]

    def get_edge_cases(self) -> List[TestRepository]:
        """Get edge case repositories"""
        return [r for r in self.repos if r.is_edge_case]

    def get_by_skill_level(self, level: SkillLevel) -> List[TestRepository]:
        """Get repositories by expected skill level"""
        return [r for r in self.repos if r.skill_level == level]

    def get_temporal_groups(self) -> Dict[str, List[TestRepository]]:
        """Get repositories grouped by temporal evolution"""
        groups = {}
        for repo in self.repos:
            if repo.temporal_group:
                if repo.temporal_group not in groups:
                    groups[repo.temporal_group] = []
                groups[repo.temporal_group].append(repo)
        return groups

    def get_dimension_specialists(self, dimension: DimensionStrength) -> List[TestRepository]:
        """Get repositories expected to be strong in a specific dimension"""
        return [r for r in self.repos if dimension in r.strong_dimensions]

    def get_comparison_pairs(self) -> Dict[str, List[TestRepository]]:
        """Get comparison pairs for relative ranking tests"""
        pairs = {}
        for repo in self.repos:
            if repo.category.startswith("comparison_pair_"):
                pair_name = repo.category
                if pair_name not in pairs:
                    pairs[pair_name] = []
                pairs[pair_name].append(repo)
        return pairs

    def get_categories(self) -> Set[str]:
        """Get all unique categories"""
        return set(r.category for r in self.repos)

    def get_stats(self) -> Dict[str, int]:
        """Get dataset statistics"""
        return {
            "total": len(self.repos),
            "ground_truth": len(self.get_ground_truth()),
            "edge_cases": len(self.get_edge_cases()),
            "categories": len(self.get_categories()),
            "platforms": len(set(r.platform for r in self.repos)),
            "novice": len(self.get_by_skill_level(SkillLevel.NOVICE)),
            "intermediate": len(self.get_by_skill_level(SkillLevel.INTERMEDIATE)),
            "senior": len(self.get_by_skill_level(SkillLevel.SENIOR)),
            "architect": len(self.get_by_skill_level(SkillLevel.ARCHITECT)),
            "expert": len(self.get_by_skill_level(SkillLevel.EXPERT)),
        }


# Create singleton instance
benchmark_dataset = BenchmarkDataset()


# ========== Helper Functions for API Routes ==========

def get_benchmark_dataset_path() -> Path:
    """Get the path to the benchmark dataset cache directory"""
    return Path.home() / ".local/share/oscanner/validation_cache"


def get_benchmark_repos_list() -> List[Dict[str, Any]]:
    """
    Get list of all benchmark repositories as dictionaries

    Returns:
        List of repository info dictionaries
    """
    repos = benchmark_dataset.get_all()
    return [
        {
            "platform": repo.platform,
            "owner": repo.owner,
            "repo": repo.repo,
            "author": repo.author,
            "identifier": repo.identifier,
            "category": repo.category,
            "skill_level": repo.skill_level.value if repo.skill_level else None,
            "expected_score_range": repo.expected_score_range,
            "is_ground_truth": repo.is_ground_truth,
            "is_edge_case": repo.is_edge_case,
            "description": repo.description,
            "public_reputation": repo.public_reputation,
        }
        for repo in repos
    ]


def load_benchmark_evaluation(
    platform: str,
    owner: str,
    repo: str,
    author: str,
    plugin_id: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Load cached benchmark evaluation for a specific repo/author

    Args:
        platform: Platform (github/gitee)
        owner: Repository owner
        repo: Repository name
        author: Author name
        plugin_id: Optional plugin ID (not currently used)

    Returns:
        Evaluation data dictionary or None if not found
    """
    import json

    cache_dir = get_benchmark_dataset_path()
    safe_name = f"{platform}_{owner}_{repo}_{author}.json"
    cache_path = cache_dir / safe_name

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading cached evaluation: {e}")
        return None
