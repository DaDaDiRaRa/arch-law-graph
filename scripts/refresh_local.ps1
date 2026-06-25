# 로컬 자동갱신 — 법제처 API가 GitHub Actions(해외 IP)를 차단해서
# 정상 동작하는 내 PC IP에서 빌드·커밋·푸시한다. Windows 작업 스케줄러로 매일 실행.
#
# 수동 실행:  powershell -ExecutionPolicy Bypass -File "D:\APPS\arch-law-graph\scripts\refresh_local.ps1"
# 로그:       D:\APPS\arch-law-graph\scripts\refresh_local.log

$ErrorActionPreference = 'Stop'

$Root   = 'D:\APPS\arch-law-graph'
$Python = 'D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe'  # networkx·httpx·dotenv 설치된 자매앱 venv
$Log    = Join-Path $Root 'scripts\refresh_local.log'

function Write-Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Output $line
    Add-Content -Path $Log -Value $line -Encoding utf8
}

try {
    Set-Location $Root
    Write-Log "=== 자동갱신 시작 ==="

    if (-not (Test-Path $Python)) { throw "Python 인터프리터 없음: $Python" }

    # 1) 갱신 전 해시 (built_at 제외)
    $before = & $Python '.github\scripts\graph_hash.py'
    Write-Log "before hash = $before"

    # 2) 빌드 — build_graph.py 는 fetch 전부 실패 시 exit 1 (빈 파일 안 씀)
    & $Python 'builder\build_graph.py'
    if ($LASTEXITCODE -ne 0) { throw "build_graph.py 실패 (exit $LASTEXITCODE) — 커밋 중단, 기존 graph.json 보존" }

    # 3) 갱신 후 해시
    $after = & $Python '.github\scripts\graph_hash.py'
    Write-Log "after  hash = $after"

    if ($before -eq $after) {
        Write-Log "법령 변경 없음 — 커밋 생략"
        Write-Log "=== 완료 ==="
        return
    }

    # 4) 변경 시에만 커밋·푸시
    Write-Log "변경 감지 — 커밋·푸시"
    git add data/graph.json
    git commit -m ("chore: 법령 데이터 자동 갱신 ({0}) [local]" -f (Get-Date -Format 'yyyy-MM-dd'))
    git push
    Write-Log "푸시 완료 — Cloud Run 재배포 트리거됨"
    Write-Log "=== 완료 ==="
}
catch {
    Write-Log ("ERROR: {0}" -f $_.Exception.Message)
    exit 1
}
