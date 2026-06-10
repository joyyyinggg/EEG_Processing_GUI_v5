# -*- coding: utf-8 -*-
"""
gui/help_content.py
===================
Help 分頁的 HTML 說明內容。
"""

HELP_HTML = """
<html>
<head>
<style>
  body  { font-family: 'Segoe UI', Arial, sans-serif; font-size:13px;
          color:#111827; background:white; margin:20px; line-height:1.7; }
  h2    { color:#2563EB; border-bottom:2px solid #DBEAFE; padding-bottom:6px; }
  h3    { color:#1D4ED8; margin-top:18px; }
  code  { background:#F3F4F6; padding:2px 6px; border-radius:4px;
          font-family:Consolas,monospace; font-size:12px; color:#DC2626; }
  table { border-collapse:collapse; width:100%; margin:10px 0; }
  th    { background:#DBEAFE; color:#1D4ED8; padding:7px 12px; text-align:left; }
  td    { padding:6px 12px; border-bottom:1px solid #E2E6EA; }
  tr:hover td { background:#F7F8FA; }
  .warn { background:#FEF3C7; border-left:4px solid #D97706;
          padding:8px 14px; border-radius:4px; margin:10px 0; }
  .info { background:#DBEAFE; border-left:4px solid #2563EB;
          padding:8px 14px; border-radius:4px; margin:10px 0; }
  ul li { margin-bottom:4px; }
</style>
</head>
<body>

<h2>EEG Preprocessing &amp; Connectivity Analysis — 使用說明</h2>

<h3>🗂 介面概覽</h3>
<table>
  <tr><th>分頁</th><th>功能說明</th></tr>
  <tr><td><b>Files</b></td><td>載入的 EEG 檔案清單，自動分為 Epilepsy 與 Normal 兩個子分頁</td></tr>
  <tr><td><b>Processing Log</b></td><td>即時顯示處理進度、錯誤訊息、ICA 排除結果</td></tr>
  <tr><td><b>Help</b></td><td>本說明頁面</td></tr>
</table>

<h3>📁 Step 1 — 選擇資料夾</h3>
<ul>
  <li>點擊左側 <b>Browse Folder</b> 選取包含 EEG .txt 的資料夾</li>
  <li>程式<b>只載入</b>檔名符合 <code>subj{數字}_{session}.txt</code> 格式的檔案（例如 <code>subj01_rest1.txt</code>）</li>
  <li>若有其他 .txt（如說明文件）不符合此格式，<b>不會被載入</b></li>
</ul>

<div class="info">
<b>受試者分組規則：</b>subj01~subj25 = Epilepsy（癲癇組），subj26 以上 = Normal（正常組）
</div>

<h3>⚙️ Step 2 — 設定參數</h3>
<table>
  <tr><th>參數</th><th>說明</th><th>建議值</th></tr>
  <tr><td>Subject Name</td><td>輸出資料夾前綴</td><td>自訂</td></tr>
  <tr><td>Epoch length (s)</td><td>單一 epoch 長度</td><td>10</td></tr>
  <tr><td>ICA components</td><td>ICA 成分數</td><td>15</td></tr>
  <tr><td>EOG threshold</td><td>眼動 IC 偵測閾值（correlation）</td><td>0.5</td></tr>
  <tr><td>EMG threshold</td><td>肌電 IC 偵測閾值（z-score）</td><td>0.7</td></tr>
  <tr><td>Bad ch limit (%)</td><td>壞通道超過此比例則跳過此筆資料</td><td>22%</td></tr>
</table>

<h3>🚀 Step 3 — 載入 MNE 資源</h3>
<ul>
  <li>點擊 <b>Load MNE Resources</b>，需要 1~3 分鐘（fsaverage + BEM + ROI labels）</li>
  <li>載入完成後 Run 按鈕才會啟用</li>
  <li><b>Epilepsy Run</b> 只跑 subj01~subj25，<b>Normal Run</b> 只跑 subj26+，<b>Run All</b> 跑全部</li>
</ul>

<h3>🔍 Step 4 — 壞通道審視視窗</h3>
<ul>
  <li>紅色通道 = LOF 自動偵測為壞通道</li>
  <li>用<b>下方滑桿</b>拖曳時間軸，<b>Scale</b> 調整振幅顯示比例</li>
  <li>右側勾選框可手動新增/移除壞通道</li>
  <li>按 <b>◀ 上一筆</b> 返回前一個檔案重新審視</li>
  <li>按 <b>確認並看下一筆 ▶</b> 確認後直接預覽下一個</li>
  <li>按 <b>跳過此筆</b> 跳過不處理</li>
</ul>

<h3>🧠 Step 5 — ICA 審視視窗</h3>
<ul>
  <li><b>IC Components 分頁</b>：上排 Topography，中排時序，下排頻譜。紅色 = 自動標記排除</li>
  <li><b>Before / After 分頁</b>：三欄對比（原始 / ICA 後 / 移除成分）</li>
  <li>勾選框可手動修改排除清單</li>
</ul>

<h3>📊 輸出結果說明</h3>
<table>
  <tr><th>檔案</th><th>說明</th></tr>
  <tr><td><code>connectome_*.png</code></td><td>3D nilearn connectome（rainbow, 0~1）</td></tr>
  <tr><td><code>view_connectome_*.png</code></td><td>2D 俯視圖（藍色線條）</td></tr>
  <tr><td><code>circle_*.png</code></td><td>Circle connectivity（rainbow, vmin=0, vmax=1）</td></tr>
  <tr><td><code>heatmap_3band.png</code></td><td>三頻帶 ROI 矩陣熱圖</td></tr>
  <tr><td><code>*.xlsx</code></td><td>Theta/Alpha/Beta 連結矩陣</td></tr>
  <tr><td><code>ICA_check/</code></td><td>ICA 前後比較圖 + IC topography</td></tr>
  <tr><td><code>所有檔案_壞通道統計.xlsx</code></td><td>每筆資料的壞通道統計</td></tr>
  <tr><td><code>所有檔案_ICA排除統計.xlsx</code></td><td>每筆資料的 ICA 排除統計</td></tr>
</table>

<div class="warn">
<b>⚠ 注意事項：</b>
資料讀入後程式<b>自動裁切前後各 30 秒</b>（<code>eeg_data[30000:-30000]</code>），
因此視窗中看到的 data 已是裁切後的版本。
若原始錄製總長為 T 秒，視窗顯示長度 = T - 60 秒。
</div>

</body>
</html>
"""
