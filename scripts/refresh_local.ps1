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
        # built_at 만 바뀐 파일을 원복해 작업 트리를 깨끗하게 유지
        git checkout -- data/graph.json
        Write-Log "법령 변경 없음 — 커밋 생략 (파일 원복)"
        Write-Log "=== 완료 ==="
        return
    }

    # 4) 카드 회귀 게이트 — 재빌드가 카드(건폐율·용적률·조경) 값을 바꿨으면 자동 커밋 차단.
    #    재빌드는 graph.json 만 바꾸므로, 카드 영향 시 추출기 재실행값이 커밋된 카드와 어긋남 →
    #    test_*_extractor_sync 실패. 자동 배포 대신 사람이 검토(gen_card_data.py 재생성 →
    #    `pytest --update-golden` 승인) 후 수동 커밋하도록 멈춘다.
    Write-Log "카드 회귀 테스트 실행 (게이트)"
    $env:PYTHONUTF8 = '1'
    $testOut = & $Python '-m' 'pytest' '-q' 2>&1
    $testOut | ForEach-Object { Write-Log "  pytest> $_" }
    if ($LASTEXITCODE -ne 0) {
        git checkout -- data/graph.json   # 재빌드 산출물 원복(작업 트리 청결, 재빌드 저렴)
        throw ("카드 회귀 테스트 실패 — 재빌드가 카드 값을 바꿨습니다. 자동 커밋 차단(graph.json 원복). " +
               "수동 검토: `python builder/build_graph.py; python builder/gen_card_data.py` 후 " +
               "diff 확인 → `pytest --update-golden` 승인 → 커밋. 위 pytest 로그에 변경된 도시/존이 찍힘.")
    }
    Write-Log "카드 회귀 테스트 통과"

    # 5) 변경 시에만 커밋·푸시
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
