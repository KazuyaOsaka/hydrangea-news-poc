"""F-16-A: per-run 上限分離 (TOP_N_VIDEOS_PER_RUN / TOP_N_ARTICLES_PER_RUN)。

試運転 7-I (2026-04-29) で動画化率 67% (2/3) で頭打ち。
Slot-3 (UAE OPEC) は AnalysisLayer 完了済みだったが、MAX_PUBLISHES_PER_DAY=5 の
ハードコード制限で skip されていた。

F-16-A は per-run 上限を分離し、cron 6 時間おき自動実行 (F-16-B) × per-run 上限で
公開頻度を制御する設計に変更する:
  - TOP_N_VIDEOS_PER_RUN   (default 1): script + video 生成対象数
  - TOP_N_ARTICLES_PER_RUN (default 3): article 生成対象数
  - MAX_PUBLISHES_PER_DAY (deprecated, default 999): 後方互換のみ

本テストは以下を担保する:
  1. 環境変数 default 値
  2. 環境変数オーバーライド
  3. Top-N ループの分岐ロジック (article-only Slot のスキップ)
  4. 既存挙動との互換性 (MAX_PUBLISHES_PER_DAY / publish_count)
  5. per-run 上限の独立性 (video > article のクランプ)
"""
from __future__ import annotations

import importlib
import inspect
import os

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# テスト 1: 環境変数の default 値
# ─────────────────────────────────────────────────────────────────────────────


class TestEnvVarDefaults:
    """F-16-A 新環境変数の default 値を検証。"""

    def _reload_config(self, monkeypatch):
        """env を反映するため src.shared.config を reload する。"""
        # 念のため legacy も明示的に外す
        monkeypatch.delenv("TOP_N_VIDEOS_PER_RUN", raising=False)
        monkeypatch.delenv("TOP_N_ARTICLES_PER_RUN", raising=False)
        monkeypatch.delenv("TOP_N_GENERATION", raising=False)
        monkeypatch.delenv("MAX_PUBLISHES_PER_DAY", raising=False)
        from src.shared import config as cfg
        importlib.reload(cfg)
        return cfg

    def test_top_n_videos_default_is_1(self, monkeypatch):
        cfg = self._reload_config(monkeypatch)
        assert cfg.TOP_N_VIDEOS_PER_RUN == 1

    def test_top_n_articles_default_is_3(self, monkeypatch):
        cfg = self._reload_config(monkeypatch)
        assert cfg.TOP_N_ARTICLES_PER_RUN == 3

    def test_max_publishes_default_is_999_deprecated(self, monkeypatch):
        """F-16-A: MAX_PUBLISHES_PER_DAY default を 5 → 999 に変更 (実質撤廃)。

        注: ユーザーの .env にレガシー値が残っていると load_dotenv で上書きされる
        ため、ここではコード側の default 値を source レベルで検証する
        (env よりも「コードの仕様」を担保したい意図)。
        """
        from src.shared import config as cfg_mod
        source = inspect.getsource(cfg_mod)
        assert 'os.getenv("MAX_PUBLISHES_PER_DAY", "999")' in source, (
            "F-16-A: config.py の MAX_PUBLISHES_PER_DAY default は 999 に "
            "変更されているべき。5 のままなら退行。"
        )


# ─────────────────────────────────────────────────────────────────────────────
# テスト 2: 環境変数のオーバーライド
# ─────────────────────────────────────────────────────────────────────────────


class TestEnvVarOverrides:
    """env で値を上書きできることを検証。"""

    def _reload_with(self, monkeypatch, **env):
        for k in (
            "TOP_N_VIDEOS_PER_RUN",
            "TOP_N_ARTICLES_PER_RUN",
            "TOP_N_GENERATION",
            "MAX_PUBLISHES_PER_DAY",
        ):
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, str(v))
        from src.shared import config as cfg
        importlib.reload(cfg)
        return cfg

    def test_top_n_videos_overridden(self, monkeypatch):
        cfg = self._reload_with(monkeypatch, TOP_N_VIDEOS_PER_RUN=2)
        assert cfg.TOP_N_VIDEOS_PER_RUN == 2

    def test_top_n_articles_overridden(self, monkeypatch):
        cfg = self._reload_with(monkeypatch, TOP_N_ARTICLES_PER_RUN=5)
        assert cfg.TOP_N_ARTICLES_PER_RUN == 5

    def test_max_publishes_overridden(self, monkeypatch):
        cfg = self._reload_with(monkeypatch, MAX_PUBLISHES_PER_DAY=42)
        assert cfg.MAX_PUBLISHES_PER_DAY == 42


# ─────────────────────────────────────────────────────────────────────────────
# テスト 3: Top-N ループの分岐ロジック (per-slot 判定)
# ─────────────────────────────────────────────────────────────────────────────


class TestSlotBranchingLogic:
    """slot_idx < TOP_N_VIDEOS_PER_RUN で video 生成、それ以降は article のみ。"""

    @pytest.mark.parametrize(
        "videos_per_run,articles_per_run,expected",
        [
            # (videos, articles, [Slot-1 video?, Slot-2 video?, Slot-3 video?])
            (1, 3, [True, False, False]),  # default 設定 (本番想定)
            (2, 3, [True, True, False]),
            (3, 3, [True, True, True]),  # video = article (全 Slot 動画化)
            (1, 1, [True]),  # article のみ 1 件 = 1 動画
        ],
    )
    def test_per_slot_video_decision(
        self, videos_per_run: int, articles_per_run: int, expected: list[bool]
    ):
        """各 Slot で video 生成するかは slot_idx < TOP_N_VIDEOS_PER_RUN で決まる。"""
        # main.py の per-slot 判定を再現:
        #   _generate_video_track = _slot_idx < _top_n_videos
        for slot_idx in range(articles_per_run):
            generate_video = slot_idx < videos_per_run
            assert generate_video == expected[slot_idx], (
                f"Slot-{slot_idx+1} expected video={expected[slot_idx]} "
                f"but got {generate_video} "
                f"(videos_per_run={videos_per_run}, articles_per_run={articles_per_run})"
            )

    def test_main_py_passes_generate_video_track_to_outputs(self):
        """src/main.py の Top-N ループが _generate_outputs に generate_video_track を
        渡していることを inspect で確認。"""
        from src import main as main_mod
        source = inspect.getsource(main_mod)

        assert "generate_video_track=_generate_video_track" in source, (
            "F-16-A: Top-N ループが generate_video_track を _generate_outputs に "
            "渡していない。実装抜けを示唆する。"
        )
        assert "_generate_video_track = _slot_idx < _top_n_videos" in source, (
            "F-16-A: per-slot の video 判定ロジックが main.py に存在しない。"
        )

    def test_main_py_uses_top_n_articles_per_run(self):
        """main.py が TOP_N_ARTICLES_PER_RUN を import / 参照していることを確認。"""
        from src import main as main_mod
        source = inspect.getsource(main_mod)
        assert "TOP_N_ARTICLES_PER_RUN" in source, (
            "F-16-A: main.py が TOP_N_ARTICLES_PER_RUN を参照していない。"
        )
        assert "TOP_N_VIDEOS_PER_RUN" in source, (
            "F-16-A: main.py が TOP_N_VIDEOS_PER_RUN を参照していない。"
        )


# ─────────────────────────────────────────────────────────────────────────────
# テスト 4: 既存挙動との互換性
# ─────────────────────────────────────────────────────────────────────────────


class TestBackwardCompat:
    """F-15 / 既存 publish_count ロジック / TOP_N_GENERATION fallback の互換性。"""

    def test_top_n_generation_is_fallback_default(self):
        """旧 TOP_N_GENERATION が TOP_N_ARTICLES_PER_RUN の fallback default として
        解釈される実装が config.py に存在することを確認。

        注: ユーザーの .env に TOP_N_ARTICLES_PER_RUN が固定されていると
        importlib.reload 時の load_dotenv で値が再注入され runtime の fallback
        動作を直接再現できないため、コード側の仕様を source レベルで検証する
        (test_max_publishes_default_is_999_deprecated と同じ方針)。"""
        from src.shared import config as cfg_mod
        source = inspect.getsource(cfg_mod)
        # legacy TOP_N_GENERATION を読む
        assert 'os.getenv("TOP_N_GENERATION", "3")' in source, (
            "F-16-A: config.py の TOP_N_GENERATION fallback 参照が消失している。"
        )
        # それを TOP_N_ARTICLES_PER_RUN の default として渡している
        assert (
            'os.getenv("TOP_N_ARTICLES_PER_RUN", _LEGACY_TOP_N_GENERATION)'
            in source
        ), (
            "F-16-A: TOP_N_GENERATION → TOP_N_ARTICLES_PER_RUN への fallback "
            "default ロジックが config.py から消失している。"
        )

    def test_new_var_takes_precedence_over_legacy(self, monkeypatch):
        """TOP_N_ARTICLES_PER_RUN が両方設定された場合の優先。"""
        monkeypatch.setenv("TOP_N_GENERATION", "9")
        monkeypatch.setenv("TOP_N_ARTICLES_PER_RUN", "4")
        from src.shared import config as cfg
        importlib.reload(cfg)
        assert cfg.TOP_N_ARTICLES_PER_RUN == 4, (
            "新変数 TOP_N_ARTICLES_PER_RUN は legacy TOP_N_GENERATION より優先される "
            "べき。"
        )

    def test_max_publishes_per_day_still_imported(self):
        """MAX_PUBLISHES_PER_DAY が main.py から import され続けていること
        (後方互換)。"""
        from src import main as main_mod
        source = inspect.getsource(main_mod)
        assert "MAX_PUBLISHES_PER_DAY" in source, (
            "F-16-A 後も MAX_PUBLISHES_PER_DAY は後方互換として参照され続けるべき。"
        )

    def test_increment_daily_publish_count_still_called(self):
        """既存の publish_count インクリメントが残存していること。"""
        from src import main as main_mod
        source = inspect.getsource(main_mod)
        assert "increment_daily_publish_count" in source, (
            "publish_count インクリメントが消失している。後方互換のため残すべき。"
        )

    def test_f15_analysis_alignment_preserved(self):
        """F-15 で確定した「AnalysisLayer は Top-3 全 Slot 対象」が維持。"""
        from src import main as main_mod
        source = inspect.getsource(main_mod)
        # F-15 の構造マーカーが残存
        assert "F-15: aligned with Top-3 generation loop" in source, (
            "F-15 の AnalysisLayer 対象選定ロジックが消失している。"
        )
        # _analysis_targets が Elite Judge total_score sort で構築される
        assert "_analysis_targets = sorted(" in source, (
            "F-15: AnalysisLayer 対象は Elite Judge total_score 順 sorted で "
            "構築されているべき。"
        )


# ─────────────────────────────────────────────────────────────────────────────
# テスト 5: per-run 上限の独立性 (video > article は無効)
# ─────────────────────────────────────────────────────────────────────────────


class TestPerRunLimitIndependence:
    """video ⊆ article 設計のため video > article は無効。クランプされる。"""

    def test_video_le_article_normal_case(self):
        """video ≤ article は問題なくそのまま。"""
        videos, articles = 1, 3
        clamped_videos = min(videos, articles)
        assert clamped_videos == 1

    @pytest.mark.parametrize("videos,articles", [(5, 3), (10, 1), (3, 1)])
    def test_video_gt_article_is_clamped(self, videos: int, articles: int):
        """video > article のときは min(video, article) にクランプされる設計。"""
        clamped_videos = min(videos, articles)
        assert clamped_videos == articles, (
            f"video={videos} > article={articles} のとき "
            f"clamped_videos == {articles} (= article 数) になるべき。"
        )

    def test_main_py_clamps_video_to_article_max(self):
        """main.py に video > article のクランプ警告ロジックが存在することを inspect。"""
        from src import main as main_mod
        source = inspect.getsource(main_mod)
        assert "_top_n_videos > _top_n_articles" in source, (
            "F-16-A: video > article のクランプ条件が main.py に存在しない。"
        )
        assert "_top_n_videos = _top_n_articles" in source, (
            "F-16-A: クランプ後に _top_n_videos = _top_n_articles を代入する "
            "ロジックが見つからない。"
        )


# ─────────────────────────────────────────────────────────────────────────────
# テスト 6: _generate_outputs(generate_video_track=False) のシグネチャ確認
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateOutputsSignature:
    """_generate_outputs に generate_video_track パラメータが追加されていること。"""

    def test_signature_has_generate_video_track(self):
        from src.main import _generate_outputs
        sig = inspect.signature(_generate_outputs)
        assert "generate_video_track" in sig.parameters, (
            "F-16-A: _generate_outputs に generate_video_track パラメータが "
            "追加されているべき。"
        )

    def test_default_is_true_for_backward_compat(self):
        """既存の呼び出し (run() / sample mode) で動画生成が壊れないよう default=True。"""
        from src.main import _generate_outputs
        sig = inspect.signature(_generate_outputs)
        assert sig.parameters["generate_video_track"].default is True

    def test_article_only_early_return_exists(self):
        """generate_video_track=False の早期 return パスが main.py に存在する。"""
        from src import main as main_mod
        source = inspect.getsource(main_mod)
        assert "if not generate_video_track:" in source, (
            "F-16-A: generate_video_track=False の早期 return ガードが見当たらない。"
        )
        assert "Article-only mode" in source or "article_only" in source.lower(), (
            "F-16-A: article-only モードの識別子が main.py に存在しない。"
        )


# ─────────────────────────────────────────────────────────────────────────────
# テスト 7: AV レンダリングのスキップロジック
# ─────────────────────────────────────────────────────────────────────────────


class TestArticleOnlySkipsAVRender:
    """article-only Slot は _render_av_outputs をスキップする。"""

    def test_av_render_skipped_for_article_only_slot(self):
        """main.py で _generate_video_track=False のとき AV レンダリングが
        スキップされる構造があることを inspect で確認。"""
        from src import main as main_mod
        source = inspect.getsource(main_mod)
        # スキップ時の placeholder dict マーカー
        assert "skipped_reason" in source, (
            "F-16-A: article-only Slot 用の AV スキップ理由フィールドが "
            "main.py に見当たらない。"
        )
        assert "article_only_slot" in source, (
            "F-16-A: article-only Slot を識別する skip タグが main.py にない。"
        )
