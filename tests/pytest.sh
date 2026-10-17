c=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

export TZ=Asia/Shanghai

cd $c/server
coverage erase
coverage  run --rcfile=.coveragerc  --branch  -m pytest

cd $c
coverage erase
coverage combine  --rcfile=.coveragerc server/.coverage 
echo =======================================================================
echo branch coverage report
echo =======================================================================
coverage report
coverage xml

cd $c/server
coverage erase
coverage  run --rcfile=.coveragerc    -m pytest
cd $c
coverage erase
coverage combine  --rcfile=.coveragerc server/.coverage 
echo =======================================================================
echo line coverage report
echo =======================================================================
coverage report
#coverage html

