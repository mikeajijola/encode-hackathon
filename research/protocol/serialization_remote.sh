#!/bin/bash
set -euo pipefail
cd /srv/serialization
case "$1" in
prepare)
    mkdir -p evidence results
    chmod 777 evidence results
    tar -xzf payload.tar.gz
    chmod -R a+rX data scorer-dataset retained
    cd repo
    git rev-parse HEAD > ../evidence/repository_commit.txt
    sudo docker version > ../evidence/docker_version.txt
    sudo docker build -t encode-serialization . > ../evidence/build.log 2>&1
    sudo docker image inspect encode-serialization > ../evidence/image_inspect.json
    sudo docker run --rm --entrypoint sh encode-serialization -c 'python --version; soffice --version' > ../evidence/runtime_versions.txt
    sudo docker run --rm --user root --entrypoint sh encode-serialization -c 'uv pip install --python /app/.venv/bin/python pytest==9.1.1 && cd /app && python -m pytest -q' > ../evidence/test_suite.log 2>&1
    cd ..
    python3 - <<'PY'
import json
from pathlib import Path
p=Path('data/manifest.json'); m=json.loads(p.read_text())
digest=json.loads(Path('evidence/image_inspect.json').read_text())[0]['Id']
m['run_config']['environment_image_digest']=digest
m['reproducibility']['container_digest']=digest
p.write_text(json.dumps(m,indent=2)+'\n')
Path('evidence/D.manifest.json').write_bytes(p.read_bytes())
PY
    sudo docker run --rm -v /srv/serialization/data:/data:ro -v /srv/serialization/results:/out encode-serialization preflight --json --record /out/container_preflight.json > evidence/preflight.log
    # Canonical offline replay, isolated from all future runtime containers.
    sudo docker run --rm --user root --entrypoint python -v /srv/serialization/scorer-dataset:/scorer:ro -v /srv/serialization/retained:/retained:ro -v /srv/serialization/evidence:/out encode-serialization -m protocol.serialization_preservation --dataset /scorer --retained /retained --output /out/offline > evidence/offline.log 2>&1
    touch evidence/prepare-complete
    ;;
run)
    test -f evidence/prepare-complete
    test -n "${GEMINI_API_KEY:-}"
    date -u +%FT%TZ > evidence/run_started.txt
    sudo --preserve-env=GEMINI_API_KEY docker run --rm --name encode-serialization-d -e GEMINI_API_KEY -v /srv/serialization/data:/data:ro -v /srv/serialization/results:/out encode-serialization run --manifest /data/manifest.json --out-dir /out/D > evidence/D.run.log 2>&1
    date -u +%FT%TZ > evidence/run_finished.txt
    ;;
score)
    test -f evidence/run_finished.txt
    sudo docker run --rm --user root --entrypoint python -v /srv/serialization/scorer-dataset:/scorer:ro -v /srv/serialization/results:/out encode-serialization -m evaluate --predictions /out/D/predictions.jsonl --dataset-dir /scorer --out /out/D/official_results.json > evidence/scoring.log 2>&1
    sudo docker run --rm --user root --entrypoint python -v /srv/serialization/results:/out encode-serialization -m protocol.mechanism_validation checkpoints --run-dir /out/D --out-dir /out/D/checkpoint-predictions
    mkdir -p results/D/checkpoint-results
    for prediction in results/D/checkpoint-predictions/*.jsonl; do
        name=$(basename "$prediction" .jsonl)
        sudo docker run --rm --user root --entrypoint python -v /srv/serialization/scorer-dataset:/scorer:ro -v /srv/serialization/results:/out encode-serialization -m evaluate --predictions "/out/D/checkpoint-predictions/$name.jsonl" --dataset-dir /scorer --out "/out/D/checkpoint-results/$name.official.json" > "evidence/$name.scoring.log" 2>&1
    done
    sudo docker run --rm --user root --entrypoint python -v /srv/serialization/results:/out encode-serialization -m protocol.mechanism_validation analyze --run-dir /out/D --official /out/D/official_results.json --checkpoint-results /out/D/checkpoint-results --out /out/D/mechanism_analysis.json
    df -h > evidence/disk_usage.txt
    free -h > evidence/memory.txt
    date -u +%FT%TZ > evidence/scoring_finished.txt
    ;;
archive)
    sudo chmod -R a+rX evidence results
    tar -czf evidence.tar.gz evidence results
    sha256sum evidence.tar.gz > evidence.tar.gz.sha256
    ;;
*) exit 2 ;;
esac
