# يقسم ملف نصوص الشاملة الكبير إلى أجزاء من 380 م.ب ليمكن نسخها إلى مساحة العمل.
# لا يغيّر الملف الأصلي، بل يقرؤه فقط. شغّله في PowerShell (ويُستحسن إغلاق الشاملة أثناءه).
$src  = "C:\shamela4\database\store\page\_2jn.fdt"
$dst  = "C:\shamela4\database\_kashshaf_parts"
$part = 380MB
New-Item -ItemType Directory -Force $dst | Out-Null
$buf = New-Object byte[] (16MB)
$in  = [IO.File]::Open($src, 'Open', 'Read', 'ReadWrite')
$i = 0
while ($in.Position -lt $in.Length) {
  $out = [IO.File]::Create(("{0}\_2jn.fdt.part{1:D2}" -f $dst, $i))
  $w = 0
  while ($w -lt $part) {
    $n = $in.Read($buf, 0, [Math]::Min($buf.Length, $part - $w))
    if ($n -le 0) { break }
    $out.Write($buf, 0, $n); $w += $n
  }
  $out.Close(); $i++
}
$in.Close()
Write-Host "Done: $i parts in $dst"
