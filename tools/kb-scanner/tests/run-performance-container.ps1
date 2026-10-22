param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Output,
    [string]$FixtureDir = 'tests/fixtures/large-project-performance',
    [switch]$Profile
)
$ErrorActionPreference = 'Stop'
$scannerRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$fixtureRoot = (Resolve-Path -LiteralPath $Source).Path
$resultRoot = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $resultRoot) { throw 'Use a new output directory, not an existing report.' }
if ($resultRoot.StartsWith($fixtureRoot.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Output must be outside fixture.' }
New-Item -ItemType Directory -Path $resultRoot | Out-Null
$imageId = docker image inspect rvport-kb-scanner-test:local --format '{{.Id}}'
if ($LASTEXITCODE -ne 0) { throw 'Independent test image unavailable; do not build a production image.' }
$revision = git -C $scannerRoot rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Scanner revision unavailable.' }
$containerName = 'kb-performance-' + [guid]::NewGuid().ToString('N')
$dockerArgs = @('create', '--name', $containerName, '--cpus', '2', '--memory', '2g', '--memory-swap', '2g',
    '--network', 'none', '--read-only', '--tmpfs', '/tmp:size=512m', '--cap-drop', 'ALL',
    '--security-opt', 'no-new-privileges', '--mount', "type=bind,source=$scannerRoot,target=/workspace/tools/kb-scanner,readonly",
    '--mount', "type=bind,source=$fixtureRoot,target=/fixture,readonly",
    '--mount', "type=bind,source=$resultRoot,target=/output", 'rvport-kb-scanner-test:local',
    'tests/run_performance_tests.py', '--source', '/fixture', '--output', '/output/benchmark',
    '--image-id', $imageId.Trim(), '--revision', $revision.Trim())
$dockerArgs += @('--fixture-dir', $FixtureDir)
if ($Profile) { $dockerArgs += '--profile' }
$createdId = docker @dockerArgs
if ($LASTEXITCODE -ne 0) { throw 'Cannot create independent performance container.' }
try {
    docker start --attach $createdId
    $scanExit = $LASTEXITCODE
    $containerState = docker inspect $createdId --format '{{json .State}}'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot retrieve container exit/OOM evidence.' }
    $containerState | Out-File -LiteralPath (Join-Path $resultRoot 'container-state.json') -Encoding utf8
} finally {
    # Only the container ID created by this invocation is removed.
    docker rm -f $createdId | Out-Null
}
exit $scanExit
