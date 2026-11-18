# 最終合併結果（2026-11-18，主 agent 彙整）

來源：lane A 的合併量測。原始資料 `results.tsv`、`correctness.txt`、`regression.txt`、`profile_before_after.txt`（同目錄），原始 log 在 `$WORK/results/final/`。

## 名詞
- grind：MFC 印出的 `Performance`，單位 ns / 格點 / 方程式 / RHS 計算，越小越好。
- loop：時間步迴圈各步牆鐘時間總和（秒）。
- PRIMARY：`5eq_rk3_weno3_hllc`，`--gbpp 160 --steps 60`，683x342x342 = 79,886,412 格、8 條方程式。
- SECONDARY：`viscous_weno5_sgb_acoustic`，`--gbpp 96 --steps 40`，577x289x289 = 48,191,617 格、8 條方程式。
- 兩個案例與官方 benchmark 只差 `parallel_io=T`。

## 配置
| 名稱 | commit / tag | 內容 |
|---|---|---|
| baseline | ce4b191d `hw-baseline` | MFC v5.7.1 原版 |
| bitwise | de73c6be `hw-opt-bitwise` | C1–C4 + B1、B2、B4；輸出與 baseline 逐位元相同 |
| full | 3c8bcc94 `hw-opt-full`（`hw-opt` HEAD） | bitwise + B3（WENO3 每側一次倒數；非逐位元） |
| baseline + case-opt | ce4b191d | 上游 `--case-optimization`（非本作業的程式碼修改） |
| full + case-opt | 3c8bcc94 | full 再加上游 `--case-optimization` |

Cherry-pick 無衝突。五個 binary 連同 md5 凍結在 `$WORK/results/final/bin/`。

## 計時（同一 H200 節點、交錯執行、各 3 次取中位數，共 24 次，無捨棄）
| 案例 | 配置 | grind (ns) | loop (s) | 相對 baseline |
|---|---|---|---|---|
| PRIMARY | baseline | 0.61386 | 69.10 | 1.000x |
| PRIMARY | bitwise | 0.34998 | 39.49 | 1.754x |
| PRIMARY | full | 0.33472 | 37.77 | 1.834x |
| PRIMARY | baseline + case-opt | 0.30540 | 34.54 | 2.010x |
| PRIMARY | full + case-opt | 0.22604 | 25.60 | 2.716x |
| SECONDARY | baseline | 1.31108 | 58.90 | 1.000x |
| SECONDARY | bitwise | 1.01565 | 45.64 | 1.291x |
| SECONDARY | full | 1.01666 | 45.65 | 1.290x |

- 三次離散：PRIMARY baseline 0.25 %、full + case-opt 0.19 %。
- full + case-opt 相對 baseline + case-opt：1.351x。
- B3 在 PRIMARY 多 4.6 %，在 SECONDARY 無增益（B3 只改 WENO3，SECONDARY 用 WENO5）。
- TSV 的 exec_s 是 mpirun 牆鐘（初始化 + 迴圈 + 一次存檔），不含 pre_process（所有 run 共用同一份 baseline 初始條件）。

## 正確性（最終步輸出對 baseline 參考輸出）
- 逐位元相同：bitwise、baseline + case-opt、baseline 重跑（兩個案例），以及 SECONDARY 的 full。
- PRIMARY 的 full 非逐位元（B3）：
  - 以場最大值正規化的最大差：6.2e-11（y/z 動量）。
  - 逐點相對差（只計數值大於場最大值 1e-6 的格點）：最大 3.4e-6，發生在動量過零點附近。
  - 能量 1.9e-10；密度與體積分率 ≤ 5.3e-8。
- full + case-opt 的輸出與 full 完全相同。
- 每個優化配置各自三次之間逐位元可重現。

## Regression（`hw-opt-full`，GPU）
指令：`./mfc.sh test --no-build --gpu acc --max-attempts 1 --only <label> -- --binary mpirun`
| label | 結果 |
|---|---|
| riemann_solver=2 | 45/45 |
| weno_order=3 | 9/9 |
| weno_order=5 | 22/22 |
| 3D（`--no-chemistry`） | 232/232 |

完整套件（`--no-chemistry`）已跑完：704 通過、0 失敗、61 跳過（共 765，耗時 52 分 40 秒；`$WORK/results/final/logs/test_full.log`）。lane B 另在 `lane-B`（B1–B4）跑過完整套件：702 通過、61 跳過，2 個雙 rank 案例需 oversubscribe 才能啟動，重跑 2/2 通過。

## 優化前後 profile（PRIMARY，nsys，10 步，同節點）
kernel 總時間 11.82 s → 6.54 s（1.81x）。
| kernel | baseline | full | 加速 |
|---|---|---|---|
| WENO3 | 6.01 s（50.8 %） | 1.65 s（25.3 %） | 3.63x |
| HLLC | 3.74 s（31.6 %） | 3.26 s（49.9 %） | 1.14x（成為最大熱點） |
| flux finalize 複製 | 0.38 s | 已移除 | |
| RK update | 0.34 s | 0.27 s | 1.28x |
| cons→prim | 0.49 s | 0.48 s（7.3 %） | 不變 |
| advection source | 0.64 s | 0.64 s（9.8 %） | 不變 |

## 結論與標題數字
- 標題數字用 bitwise 配置：PRIMARY 1.75x、SECONDARY 1.29x，輸出與原版逐位元相同。
- full（加 B3）為 PRIMARY 1.83x，另列並註明非逐位元。
- 疊加上游 `--case-optimization` 後 PRIMARY 2.72x；其中上游功能單獨為 2.01x，本作業的修改在其上再貢獻 1.35x。
- 未納入最終版、僅有單線量測的候選：E1（`lane-B-e1` 75f1ca8e，HLLC / cons→prim 固定尺寸，−5.6 %，逐位元，riemann_solver=2 45/45）、B5（WENO5 除法 28→4，WENO5 版案例 −12.2 %，非逐位元，未跑 regression）。
- 下一步：HLLC 現佔 49.9 %，每執行緒 196 個暫存器使 occupancy 只有 12.5 %，是下一個目標。

## 限制
- 只在單一 GPU、單一 MPI rank 量測；未測多 GPU 與弱/強擴展。
- SECONDARY 在 40 步內幾乎不演化，正確性判斷主要依賴 PRIMARY 與 regression 套件。
- regression 一律 `--no-chemistry`（chemistry 變體未 build）。
- 各 lane 的單項增益是在較小網格、另一節點量的，與本表不可直接相加。
