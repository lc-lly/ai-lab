# 调试前自动释放 8000 端口（preLaunchTask）
#
# 两种占用形态，必须分别处理：
#
#  A. 正常存活：uvicorn --reload 的进程树是
#         uvicorn.exe(启动器) -> python(reloader) -> python(server, 持端口) -> python(spawn子进程)
#     只杀持端口的 server 没用 —— reloader 会立刻重新拉起一个，端口照样被占。
#     所以要先沿父链回溯到这棵树的根，再用 taskkill /T 整棵杀。
#
#  B. 孤儿残留：父进程被杀后，子进程会带着继承来的监听 socket 句柄活下来，
#     此时 netstat 显示的端口归属仍是那个已经死掉的 PID —— 按 PID 杀完全无效。
#     只能按 "--multiprocessing-fork" 特征去找这些孤儿进程。
#
# 注意：输出刻意用英文。Windows PowerShell 5.1 默认以 ANSI/GBK 写控制台，
#       而 VSCode 集成终端按 UTF-8 解读，中文运行输出会直接乱码。
#       本文件含中文注释，必须以 UTF-8 with BOM 保存，否则 PS 5.1 会读乱。

$ErrorActionPreference = 'SilentlyContinue'
$Port = 8000
$killed = @()

function Get-PortOwner {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

# 沿父链回溯到进程树的根，但只在 python/uvicorn 之间走，
# 避免一路走到 shell / VSCode 进程上去把它们也杀了。
function Get-ServerRoot([int]$ProcId) {
    $current = $ProcId
    for ($i = 0; $i -lt 10; $i++) {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$current" -EA SilentlyContinue
        if (-not $p) { break }
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)" -EA SilentlyContinue
        if (-not $parent) { break }
        if ($parent.Name -notin @('python.exe', 'uvicorn.exe')) { break }
        $current = $parent.ProcessId
    }
    return $current
}

# 孤儿 spawn 子进程：带 --multiprocessing-fork 特征且父进程已退出。
# 用这个精确特征（而不是宽泛的 multiprocessing）是为了不误伤其他 python 进程。
function Get-OrphanServer {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -EA SilentlyContinue |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -match '--multiprocessing-fork' -and
            -not (Get-Process -Id $_.ParentProcessId -EA SilentlyContinue)
        }
}

for ($round = 1; $round -le 3; $round++) {
    if (-not (Get-PortOwner)) { break }

    foreach ($ownerPid in Get-PortOwner) {
        if (-not (Get-Process -Id $ownerPid -EA SilentlyContinue)) { continue }
        $root = Get-ServerRoot $ownerPid
        if ($root -eq $ownerPid) {
            Write-Host "[kill-port] port $Port held by PID $ownerPid - terminating"
        } else {
            Write-Host "[kill-port] port $Port held by PID $ownerPid (tree root $root) - terminating whole tree"
        }
        & taskkill /T /F /PID $root | Out-Null
        $killed += $root
    }

    Start-Sleep -Milliseconds 800

    # 杀掉父进程后，被继承的 server 子进程才变成孤儿，所以要在这之后再扫一次
    foreach ($orphan in Get-OrphanServer) {
        Write-Host "[kill-port] orphan PID $($orphan.ProcessId) (parent $($orphan.ParentProcessId) exited, still holds inherited socket) - terminating"
        Stop-Process -Id $orphan.ProcessId -Force
        $killed += $orphan.ProcessId
        Start-Sleep -Milliseconds 600
    }
}

if (Get-PortOwner) {
    Write-Host "[kill-port] FAILED: port $Port still in use, debug cannot start" -ForegroundColor Red
    Get-NetTCPConnection -LocalPort $Port -State Listen | Format-Table LocalAddress, OwningProcess
    exit 1
}

if ($killed.Count) {
    Write-Host "[kill-port] port $Port released (killed tree roots: $(($killed | Sort-Object -Unique) -join ', '))" -ForegroundColor Green
} else {
    Write-Host "[kill-port] port $Port is free, nothing to clean" -ForegroundColor Green
}
exit 0
