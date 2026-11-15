"""Generate small valid one-page PDFs for demonstration uploads."""
from pathlib import Path


def pdf(text):
    stream=("BT /F1 16 Tf 60 760 Td ("+text+") Tj ET\n").encode("ascii")
    objects=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"endstream"]
    result=bytearray(b"%PDF-1.4\n")
    offsets=[0]
    for number,obj in enumerate(objects,1):
        offsets.append(len(result))
        result.extend(str(number).encode()+b" 0 obj\n"+obj+b"\nendobj\n")
    start=len(result)
    result.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"+str(start).encode()+b"\n%%EOF\n")
    return result


if __name__=="__main__":
    root=Path(__file__).resolve().parents[1]/"examples"
    root.mkdir(exist_ok=True)
    for name,text in [("transcript.pdf","Teaching transcript - synthetic demo data only"),("proof.pdf","Teaching proof document - synthetic demo data only")]:
        (root/name).write_bytes(pdf(text))
        print(root/name)
