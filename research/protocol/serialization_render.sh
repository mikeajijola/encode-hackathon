#!/bin/bash
set -euo pipefail
cd /srv/serialization
sudo apt-get install -y poppler-utils > evidence/render_dependencies.log 2>&1
for task in 58147 61-4; do
    for variant in original ordinary_openpyxl raw_xml_value_reconstruction; do
        directory="/srv/serialization/evidence/renders/$task/$variant"
        mkdir -p "$directory"
        chmod 777 "$directory"
        sudo docker run --rm --tmpfs /home/runner:rw,exec,nosuid,uid=999,gid=999 --tmpfs /tmp:rw,exec,nosuid,size=1g --entrypoint soffice -v /srv/serialization/evidence/offline:/inputs:ro -v "$directory":/out encode-serialization --headless --convert-to pdf --outdir /out "/inputs/$task/$variant.xlsx" > "$directory/render.log" 2>&1
        pdfinfo "$directory/$variant.pdf" > "$directory/pdfinfo.txt"
        pdftotext -layout "$directory/$variant.pdf" "$directory/text.txt"
        pdftoppm -f 1 -l 1 -scale-to 1600 -png -singlefile "$directory/$variant.pdf" "$directory/page-1"
    done
done
find evidence/renders -type f -exec sha256sum {} + > evidence/render_checksums.txt
