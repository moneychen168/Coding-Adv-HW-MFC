# 講稿：MFC 在 NVIDIA H200 上的 GPU 效能優化

作者：moneychen168　｜　共 16 頁　｜　總字數 1615（中文 1248 字）；影片旁白總長 7.6 分鐘（459 秒）

> 本檔由 `deliverables_src/content.yaml` 自動產生，請改內容檔後重跑 `make_all.sh`。技術名詞（kernel、launch、WENO、Riemann solver、grindtime、profiling…）保留英文。

自創代號：**MFC** = Multi-component Flow Code（本作業優化的程式）；**grindtime** = MFC 官方效能指標，每格點、每方程、每次 RHS 計算的平均耗時（ns）；**RHS** = right-hand side，半離散方程的右手邊項；**WENO** = Weighted Essentially Non-Oscillatory 高階重建；**HLLC** = Harten–Lax–van Leer–Contact 近似 Riemann solver；**RK3** = 三階 Runge–Kutta 時間積分；**lane A/B/C/D** = 四條平行工作線（見第 13 頁）；**per-lane A/B** = 各 lane 在自己的較小網格與節點上做的前後對照；**hw-opt-bitwise** = C1–C4 + B1、B2、B4（輸出與 baseline 逐位元相同）；**hw-opt-full** = hw-opt-bitwise + B3；**case-opt** = MFC 內建的 --case-optimization 編譯選項。

## 第 1 頁｜MFC 在單張 H200 上的 GPU 效能優化｜grindtime 1.75×，輸出逐位元相同

大家好。這份作業選的是 MFC，一套用 Fortran 和 OpenACC 寫的可壓縮多相流求解器，目標是在國網 Nano 的單張 H200 上把它變快，指標是官方的 grindtime。結果是：在輸出和原版逐位元相同的前提下，主要測資快了 1.75 倍，第二個測資快了 1.29 倍；再加上 MFC 內建的 case-optimization，總共 2.72 倍。整份作業由多個 AI agent 分工完成。

<sub>（123 字，其中中文 98 字，旁白 35 秒）</sub>

## 第 2 頁｜MFC：約 4 萬行 Fortran 的可壓縮多相流求解器，GPU 用 OpenACC

MFC 全名是 Multi-component Flow Code，由 Georgia Tech 開發，大約四萬行 Fortran，GPU 部分是 OpenACC 指令，曾入圍 2025 年的 Gordon Bell 獎。我們只優化負責時間推進的 simulation 程式。它每一步做五件事：變數轉換、WENO 重建、用 Riemann solver 算格面通量、加總得到右手邊，最後用三階 Runge-Kutta 更新，每一步要算三次右手邊。

<sub>（110 字，其中中文 80 字，旁白 31 秒）</sub>

## 第 3 頁｜度量：grindtime = 每格點 · 每方程 · 每次 RHS 的耗時（ns）

grindtime 是 MFC 官方的效能指標：一個 Runge-Kutta stage 的最短牆鐘時間，除以方程數和格點數，也就是每格點、每方程、每次右手邊幾奈秒，越低越快。主要測資是官方 benchmark，3D 震波撞擊水滴，約八千萬格、8 條方程、跑 60 步。

<sub>（90 字，其中中文 70 字，旁白 23 秒）</sub>

## 第 4 頁｜環境：國網 Nano 單張 H200 + NVHPC 26.3（OpenACC）

環境是國網 Nano 的單張 H200，編譯器是 NVHPC 26.3，起點是 MFC 5.7.1 正式版。所有運算都在預先配置的佔位 job 裡執行，各條工作線用同一支量測腳本。

<sub>（59 字，其中中文 47 字，旁白 18 秒）</sub>

## 第 5 頁｜Baseline：未修改的 MFC v5.7.1，grindtime 0.61395 ns

Baseline 是沒有修改的 MFC。主要測資的 grindtime 中位數是 0.61395 奈秒，三次只差 0.17%，而且三次輸出逐位元相同，可以重現。

<sub>（46 字，其中中文 36 字，旁白 15 秒）</sub>

## 第 6 頁｜Profile：WENO3 重建佔 50.8%、HLLC Riemann solver 佔 31.6%

Profile 顯示，WENO 三階重建佔 50.8%，HLLC Riemann solver 佔 31.6%，合計超過八成。HLLC 每個執行緒用 196 個暫存器，occupancy 只有 12.5%。GPU 在迴圈裡百分之百忙碌，瓶頸在 kernel 本身，所以 B 線攻 WENO，C 線攻 Riemann solver。

<sub>（75 字，其中中文 47 字，旁白 27 秒）</sub>

## 第 7 頁｜B1：WENO3 kernel 的 private 陣列改純量、調整迴圈順序，grindtime −35.1%

以下三頁是各線在較小網格上的前後對照。第一項在 WENO kernel：中間值原本存在執行時才決定大小的 private 陣列，在 GPU 上變成每個執行緒的記憶體暫存，存取也不連續。改成純量並調整迴圈順序後，浮點順序不變，grindtime 從 0.6286 降到 0.4079 奈秒，快了 1.541 倍，輸出逐位元相同。B4 用同樣方法修好五階和七階，五階快了 32.2%。

<sub>（132 字，其中中文 110 字，旁白 35 秒）</sub>

## 第 8 頁｜case-optimization 2.03×；再加 C1–C4，合計 2.40×（逐位元相同）

C 線先試 MFC 內建的 case-optimization，把測資參數寫死進執行檔，快了 2.03 倍，輸出逐位元相同。接著四個小改動：HLLC 直接寫最終通量、Runge-Kutta 一格一執行緒、放寬 inline 上限、EOS 捷徑，累計快 7.5%，也都逐位元相同。

<sub>（83 字，其中中文 63 字，旁白 24 秒）</sub>

## 第 9 頁｜B2 + B3：跳過橫向 ghost 層的重建、WENO3 權重少做除法

第三組是兩個較小的 WENO 優化。B2 發現 Riemann solver 只讀內部格點，所以不再對橫向的 ghost 層做重建，快了 1.1%，輸出逐位元相同。B3 把非線性權重的除法從每格 16 次減到 4 次，快了 3.6%，但它改變浮點順序，最大相對誤差 3.7e-10，所以只放進另一個設定 hw-opt-full。

<sub>（104 字，其中中文 82 字，旁白 30 秒）</sub>

## 第 10 頁｜試過但沒有採用：沒變快、或破壞正確性的方向

不是每個想法都有效。全域限制暫存器數讓 occupancy 提高，卻沒有變快；把 EOS helper 改成 public 想促成 inline，device code 完全沒變；B4 對三階 WENO 也沒有幫助。這些都照實記錄在報告裡。

<sub>（70 字，其中中文 54 字，旁白 20 秒）</sub>

## 第 11 頁｜總結果：bitwise 1.75×（逐位元相同）、full 1.83×、加上游 case-opt 2.72×

最終結果在同一個 H200 節點上交錯重量，每個設定跑三次取中位數。輸出和原版逐位元相同的 bitwise 設定，主要測資快 1.75 倍，第二個測資快 1.29 倍。加入 B3 的 full 設定是 1.83 倍，但不是逐位元相同。上游的 case-optimization 單獨是 2.01 倍，我們的改動疊在上面再快 1.35 倍，合計 2.72 倍。

<sub>（110 字，其中中文 89 字，旁白 30 秒）</sub>

## 第 12 頁｜優化前後的 kernel 時間：WENO3 快 3.63×，HLLC 成為最大熱點

用 nsys 比較優化前後，kernel 總時間從 11.82 秒降到 6.54 秒。WENO 三階快了 3.63 倍，finalize 的全場複製直接消失；HLLC 只快 1.14 倍，現在佔了將近一半，是下一個目標。

<sub>（62 字，其中中文 46 字，旁白 20 秒）</sub>

## 第 13 頁｜正確性：輸出比對 + MFC regression test，兩關都過才算數

每個優化都要過兩關：逐變數比對最後的守恆變數，以及 MFC 內建的 regression test。bitwise 設定在兩個測資都和原版逐位元相同。full 設定因為 B3 不是：以場最大值正規化的最大差是 6.2e-11，逐點相對差最大 3.4e-6，出現在動量接近零的地方。regression 子集 45、9、22、232 個測試全部通過；完整套件 704 個測試，704 個通過、0 個失敗。

<sub>（132 字，其中中文 101 字，旁白 38 秒）</sub>

## 第 14 頁｜一個主 agent 當大腦，四條 lane 平行工作

接下來說明怎麼用 AI agent。一個 Fable 5.2 主 agent 當大腦，只做決策、派工和整合，不自己改程式。四條平行工作線：A 線負責 build、baseline、profile 和最終整合；B 線攻 WENO；C 線攻 Riemann solver、time stepper 和 build 選項；D 線自動產生簡報、影片和報告。實作的 agent 用 Opus 5.5 和 Fable 5.2。

<sub>（106 字，其中中文 68 字，旁白 31 秒）</sub>

## 第 15 頁｜讓多個 agent 平行又不互相破壞的規則

規則有三條：主 agent 預先配置佔位 job，其他 agent 只能用 srun 進去跑，不在登入節點運算、也不自己送 job；每條線改不同檔案，每個優化是獨立 commit；先驗證再報數字，失敗也照實記錄。共同的坑，例如 git hook 在登入節點跑檢查、每次執行寫出 29 GB，踩到一次就寫進共享日誌，其他線就不會再踩。主 agent 也做了幾個關鍵決定：不是逐位元相同的 B3 單獨成一個設定，上游的 case-optimization 和我們的改動分開報告，還沒驗證完的 E1 和 B5 不放進最終版。

<sub>（185 字，其中中文 152 字，旁白 43 秒）</sub>

## 第 16 頁｜總結：輸出逐位元相同下 1.75×；加上游 case-opt 2.72×

總結。在輸出和原版逐位元相同的前提下，主要測資快 1.75 倍、第二個測資快 1.29 倍，加上上游的 case-optimization 是 2.72 倍。最大的收穫是看 profile 的暫存器和 occupancy，而不是憑直覺；逐位元比對讓每個改動都能單獨判斷。不足也寫進報告：只測單一 GPU、兩個候選沒有整合，agent 也在登入節點誤觸過兩次 git hook。謝謝大家。

<sub>（128 字，其中中文 105 字，旁白 35 秒）</sub>
