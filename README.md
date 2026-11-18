# MFC 在 NVIDIA H200 上的 GPU 效能優化（Coding-Adv-HW）

作者：moneychen168｜repo：<https://github.com/moneychen168/Coding-Adv-HW-MFC>

選 MFC（Multi-component Flow Code，Fortran + OpenACC 的可壓縮多相流求解器）v5.7.1，在國網 Nano 的單張 NVIDIA H200 上做 coding 層級的效能優化。
效能指標是 MFC 官方的 grindtime：每格點、每方程、每次 RHS（right-hand side）計算的平均耗時，單位 ns，越低越快（定義見 `report.md` 4.2）。

## 結果（`results/final/`：同一 H200 節點交錯執行，各 3 次取中位數）

| 測資 | 設定 | grindtime（ns） | 相對 baseline | 輸出 |
|---|---|---|---|---|
| PRIMARY（`5eq_rk3_weno3_hllc`，683×342×342） | baseline（MFC v5.7.1） | 0.61386 | 1.00× | — |
| PRIMARY | **hw-opt-bitwise** | **0.34998** | **1.75×** | 與原版逐位元相同 |
| PRIMARY | hw-opt-full（+B3） | 0.33472 | 1.83× | 非逐位元：最大差 6.2e-11（場最大值正規化）、逐點 3.4e-6 |
| PRIMARY | baseline + 上游 `--case-optimization` | 0.30540 | 2.01× | 與原版逐位元相同 |
| PRIMARY | hw-opt-full + `--case-optimization` | 0.22604 | 2.72× | 與 hw-opt-full 相同（我們的改動在 case-opt 之上再 1.35×） |
| SECONDARY（`viscous_weno5_sgb_acoustic`，577×289×289） | hw-opt-bitwise | 1.01565（baseline 1.31108） | 1.29× | 與原版逐位元相同 |

- hw-opt-bitwise = C1–C4 + B1、B2、B4；hw-opt-full = hw-opt-bitwise + B3。各項改動見 `report.md` 第 7 節。
- 正確性：hw-opt-full 的 MFC regression 完整套件（GPU、`--no-chemistry`）704 passed / 0 failed / 61 skipped；子集 riemann_solver=2 45/45、weno_order=3 9/9、weno_order=5 22/22、3D 232/232（`results/final/regression.txt`）。
- 詳細報告：`report.md`（PDF：`docs/report.pdf`）；投影片、講稿、字幕：`docs/slides.pptx`、`docs/speech.md`、`docs/video.srt`。報告影片（mp4）另行繳交，不放在 repo。

## Repo 結構

| 位置 | 內容 |
|---|---|
| branch `hw-opt` | 優化後的 MFC 原始碼（比較檢視：`hw-baseline...hw-opt`）；tags：`hw-baseline`（`ce4b191d`，MFC v5.7.1 原版）、`hw-opt-bitwise`（`af7470e6`）、`hw-opt-full`（`933e55ba`，branch HEAD） |
| branch `main` | 作業資料（下表） |

branch `main`：

| 路徑 | 內容 |
|---|---|
| `README.md`、`report.md` | 本說明、詳細報告 |
| `docs/` | `report.pdf`、`slides.pptx`、`speech.md`、`video.srt`、報告用圖 `figs/` |
| `results/` | 各 lane 的量測摘要（`B/summary.md`、`C/results.tsv`）與最終合併結果 `final/`（`summary.md`、`results.tsv`、`correctness.txt`、`regression.txt`、`profile_before_after.txt`） |
| `jobs/` | `env.sh`（NVHPC 26.3、`MFC_CUDA_CC=90`）、`run_bench.sh`（量測）、`profile_A.sh`、`ncu_A.sh`、佔位 job 腳本 |
| `tools/compare_output.py` | 兩次 simulation 輸出的逐變數比對（最大絕對 / 相對差、是否逐位元相同） |
| `cases/` | 量測用 case 檔（與官方 benchmark 只差 `parallel_io=T`） |
| `deliverables_src/` | 交付物管線：`content.yaml` → 投影片、旁白影片、字幕、報告 PDF |
| `AGENT_LOG.md` | 多 agent 共享工作日誌（只附加） |

## 重現

所有運算都在 H200 計算節點上做（login node 不運算）。路徑以兩個變數表示：

- `$HW`：本 repo（branch `main`）的根目錄。
- `$WORK`：大檔工作目錄（MFC 原始碼與 build、量測輸出、交付物 mp4 / pdf），放在叢集的大容量檔案系統。

```bash
export HW=<本 repo 路徑>  WORK=<大檔工作目錄>
# 1) 取得優化後的 MFC（branch hw-opt；原版用 tag hw-baseline）
git clone -b hw-opt https://github.com/moneychen168/Coding-Adv-HW-MFC $WORK/MFC
# 2) 環境與 build（在計算節點上；module 只在 login shell 存在，所以用 bash -lc）
source $HW/jobs/env.sh
cd $WORK/MFC && ./mfc.sh build --gpu acc -j 12 -t pre_process simulation
#    case-optimization 版本：./mfc.sh build --gpu acc -t simulation --case-optimization --input <case.py>
# 3) 量測（例：PRIMARY）
$HW/jobs/run_bench.sh $WORK/MFC $HW/cases/5eq_rk3_weno3_hllc/case.py <outdir> --gbpp 160 --steps 60
# 4) 輸出比對（MFC venv 的 python；系統 python3 沒有 numpy）
$WORK/MFC/build/venv/bin/python3 $HW/tools/compare_output.py <baseline_run> <optimized_run>
# 5) regression test（在 srun step 內需讓 mpirun 可 oversubscribe）
OMPI_MCA_rmaps_base_oversubscribe=true ./mfc.sh test --no-build --gpu acc --no-chemistry -- --binary mpirun
```

交付物（login node 只做 TTS 網路請求；渲染在佔位 job 內以 srun 執行）：

```bash
bash $HW/deliverables_src/make_all.sh                                   # 全部重生
STAGES="pptx png" SKIP_TTS=1 bash $HW/deliverables_src/make_all.sh       # 只重做部分階段
```
