#!/usr/bin/env python3
"""Deterministic, offline plugin build. Never modifies sources or user HOME.

All eight skills receive generated copies. A minimal portable manifest and the
Codex compatibility manifest are derived from the one identity source. Existing
generated files must match their previous manifest before they can be replaced.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import re
import sys
import zipfile

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"runtime"))
from minds.contracts import strict_loads,validate_shape,schema
from minds.errors import MindsError,fail

DENIED={".git",".env","holdout","runs","__pycache__","baseline","08_baseline","credentials","config.toml","tests"}
ABSOLUTE=re.compile(r"(?i)(?:\b[a-z]:[\\/]|/Users/|/home/)")

def digest(data): return hashlib.sha256(data).hexdigest()
def json_bytes(value): return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")

def safe_tree(path):
    """Reject symlinks and Windows junction/reparse points before read/write."""
    for entry in [path,*path.parents]:
        if entry.exists() and (entry.is_symlink() or (hasattr(entry,"is_junction") and entry.is_junction()) or getattr(entry.lstat(),"st_file_attributes",0)&0x400):
            fail("E_SYMLINK","构建路径包含链接或重解析点。")

def text_bytes(path):
    safe_tree(path)
    text=path.read_text(encoding="utf-8-sig").replace("\r\n","\n").replace("\r","\n")
    if ABSOLUTE.search(text): fail("E_PATH_ESCAPE","发布输入包含开发机绝对路径："+path.name)
    return text.encode("utf-8")

def collect(source_root):
    source_root=Path(source_root).resolve(); src=source_root/"source"
    for base in (src,source_root/"runtime"):
        safe_tree(base)
        for f in base.rglob("*"):
            safe_tree(f)
            if any(part.lower() in DENIED or part.lower().startswith(".env.") for part in f.relative_to(base).parts):
                fail("E_SEMANTIC","发布源包含禁止的路径："+f.relative_to(base).as_posix())
    identity=strict_loads((src/"plugin/identity.json").read_text("utf-8"))
    if identity["name"]!="16-minds" or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?",identity["version"]): fail("E_SCHEMA","插件身份或版本非法。")
    reg=strict_loads((src/"commands/registry.json").read_text("utf-8"))
    expected={"one":"minds-one","many":"minds","pair":"minds-pair","cast":"minds-cast","write":"minds-write","decide":"minds-decide","vote":"minds-vote","ask":"minds-ask"}
    if len(reg["commands"])!=8 or {e["workflow"]:e["skill"] for e in reg["commands"]}!=expected: fail("E_SCHEMA","八入口注册表不完整。")
    if set(p.stem for p in (src/"personas").glob("*.json"))!=set(reg["personas"]) or len(reg["personas"])!=16: fail("E_SCHEMA","必须有完整十六人格。")
    if set(p.name for p in (src/"skills").iterdir())!=set(expected.values()): fail("E_SCHEMA","技能目录与八入口不一致。")
    for pid in reg["personas"]:
        persona=strict_loads((src/"personas"/(pid+".json")).read_text("utf-8")); validate_shape("persona",persona)
        if persona["id"]!=pid or not persona["source_map"] or not (src/persona["common_competence_ref"]).is_file(): fail("E_SCHEMA","人格身份、溯源或公共政策引用无效。")
    resources={}
    for directory in ("personas","references","workflows","commands","adapters","profiles","security","casting"):
        for f in sorted((src/directory).rglob("*")):
            if f.is_file(): resources[f.relative_to(src).as_posix()]=text_bytes(f)
    for f in sorted((src/"contracts/schemas").glob("*.json")):
        # Compile/check every project's supported schema before packaging.
        from minds.contracts import _check_schema
        _check_schema(strict_loads(f.read_text("utf-8")))
        resources[f.relative_to(src).as_posix()]=text_bytes(f)
    for f in sorted((src/"contracts").glob("*.json")):
        resources[f.relative_to(src).as_posix()]=text_bytes(f)
    resources["plugin/identity.json"]=text_bytes(src/"plugin/identity.json")
    runtime={p.name:text_bytes(p) for p in sorted((source_root/"runtime/minds").glob("*.py"))}
    if not {"cli.py","normalize.py","contracts.py","state.py","personas.py","__init__.py"}<=runtime.keys(): fail("E_SCHEMA","helper 模块不完整。")
    files={}
    portable={"$schema":"https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",**{k:identity[k] for k in ("name","version","description")}}
    files["plugin.json"]=json_bytes(portable)
    files[".codex-plugin/plugin.json"]=json_bytes({**identity,"skills":"./skills/"})
    for name in ("LICENSE","ATTRIBUTION.md","persona-provenance.json"): files[name]=text_bytes(src/"plugin"/name)
    helper=("from pathlib import Path\nimport sys\nsys.dont_write_bytecode = True\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parent))\n"
        "from minds_runtime.cli import main\nraise SystemExit(main())\n").encode("utf-8")
    for entry in reg["commands"]:
        name=entry["skill"]; prefix="skills/"+name+"/"
        skill=text_bytes(src/"skills"/name/"SKILL.md")
        if not skill.startswith(b"---\n") or ("name: "+name+"\n").encode() not in skill or b"description:" not in skill: fail("E_SCHEMA","SKILL frontmatter 非法。")
        files[prefix+"SKILL.md"]=skill
        files[prefix+"scripts/minds_cli.py"]=helper
        for rel,content in resources.items(): files[prefix+"references/"+rel]=content
        for rel,content in runtime.items(): files[prefix+"scripts/minds_runtime/"+rel]=content
    # Resolve markdown references only where the instruction text makes them executable.
    for rel,content in files.items():
        if rel.endswith("SKILL.md"):
            for target in re.findall(r"\]\(([^)]+)\)",content.decode("utf-8")):
                target_path=(Path(rel).parent/target).as_posix()
                if target_path not in files: fail("E_SCHEMA","技能引用未随包提供。")
    inputs={}
    for base in (src,source_root/"runtime/minds"):
        for f in sorted(base.rglob("*")):
            if f.is_file(): inputs[f.relative_to(source_root).as_posix()]=digest(text_bytes(f))
    return identity,files,inputs

def verify_existing(output_root):
    if not output_root.exists(): return
    safe_tree(output_root)
    actual={p.relative_to(output_root).as_posix():p for p in output_root.rglob("*") if p.is_file()}
    if not actual: return
    if "build-manifest.json" not in actual: fail("E_EXISTS","输出目录非空且没有构建清单；拒绝覆盖。")
    manifest=strict_loads(actual["build-manifest.json"].read_text("utf-8"))
    expected=manifest.get("files",{})
    if set(actual)!=set(expected)|{"build-manifest.json"}: fail("E_EXISTS","生成目录包含未登记或缺失文件；拒绝覆盖。")
    for rel,file in actual.items():
        safe_tree(file)
        if rel!="build-manifest.json" and digest(file.read_bytes())!=expected[rel]: fail("E_EXISTS","生成文件被手工修改；拒绝覆盖："+rel)

def verify_dist(dist, new_zip_name):
    """Check previous generated archives before any build writes, preserve edits."""
    safe_tree(dist)
    metadata=dist/"build-manifest.json"
    if not metadata.exists():
        if (dist/new_zip_name).exists() or (dist/"marketplace.json").exists():
            fail("E_EXISTS","dist 已存在无可验证清单的产物；拒绝覆盖。")
        return
    safe_tree(metadata)
    prior=strict_loads(metadata.read_text("utf-8"))
    archive=prior.get("archive",{})
    filename=archive.get("file")
    if not isinstance(filename,str) or Path(filename).name!=filename or "\\" in filename or ":" in filename:
        fail("E_PATH_ESCAPE","dist archive 名称不安全。")
    target=dist/filename;safe_tree(target)
    if not target.is_file() or digest(target.read_bytes())!=archive.get("sha256"):
        fail("E_EXISTS","已有 dist ZIP 已修改或缺失；拒绝覆盖。")
    try:
        with zipfile.ZipFile(target) as z:
            if z.testzip() is not None: fail("E_EXISTS","已有 dist ZIP CRC 错误。")
            expected={"16-minds/"+x for x in prior["files"]}|{"16-minds/build-manifest.json"}
            if len(z.namelist())!=len(expected) or set(z.namelist())!=expected: fail("E_EXISTS","已有 dist ZIP 清单不一致。")
            inside=strict_loads(z.read("16-minds/build-manifest.json").decode("utf-8"))
            if inside!={k:v for k,v in prior.items() if k!="archive"}: fail("E_EXISTS","dist 元数据与包内清单不一致。")
            if any(digest(z.read("16-minds/"+name))!=h for name,h in prior["files"].items()): fail("E_EXISTS","已有 dist 成员被修改。")
    except (OSError,ValueError,KeyError,zipfile.BadZipFile):
        fail("E_EXISTS","已有 dist 产物不可验证；保留现场。")
    if filename!=new_zip_name and (dist/new_zip_name).exists(): fail("E_EXISTS","新版本名称已被占用，拒绝覆盖。")
    catalog=dist/"marketplace.json"
    if catalog.exists():
        safe_tree(catalog)
        expected={"name":"16minds-local","interface":{"displayName":"16 Minds Local"},"plugins":[{"name":"16-minds","source":{"source":"local","path":"./plugins/16-minds"},"policy":{"installation":"AVAILABLE","authentication":"ON_INSTALL"},"category":"Productivity"}]}
        if strict_loads(catalog.read_text("utf-8"))!=expected: fail("E_EXISTS","已有 dist marketplace 已修改，拒绝覆盖。")

def make_zip(files):
    stream=io.BytesIO()
    # Stored entries avoid compression-library differences across machines.
    with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_STORED) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo("16-minds/"+name,(1980,1,1,0,0,0)); info.create_system=3
            info.external_attr=0o100644<<16; info.compress_type=zipfile.ZIP_STORED
            archive.writestr(info,data)
    return stream.getvalue()

def build(source_root=ROOT,output_root=None,resource_strategy="per_skill"):
    source_root=Path(source_root).resolve()
    output_root=Path(output_root or source_root/"plugins/16-minds").absolute()
    safe_tree(output_root)
    output_root=output_root.resolve()
    if not output_root.is_relative_to(source_root) or output_root==source_root or output_root.is_relative_to(source_root/"source") or output_root.is_relative_to(source_root/"runtime"):
        fail("E_PATH_ESCAPE","构建输出必须在开发目录的生成路径内。")
    if output_root.name!="16-minds": fail("E_SCHEMA","输出目录名必须是 16-minds。")
    if resource_strategy!="per_skill": fail("E_CAPABILITY","相邻 skill 资源共享未经宿主验证；仅支持每入口自包含构建。")
    identity,files,inputs=collect(source_root)
    manifest={"manifest_version":"1.0.0","plugin":identity["name"],"version":identity["version"],"release_level":"static_candidate",
        "resource_strategy":resource_strategy,"source_hashes":inputs,"files":{k:digest(v) for k,v in sorted(files.items())},
        "zip_metadata":{"timestamp":"1980-01-01T00:00:00","compression":"stored","unix_mode":"100644"}}
    files["build-manifest.json"]=json_bytes(manifest)
    verify_existing(output_root)
    zip_name=f"16-minds-{identity['version']}-static_candidate.zip"
    dist=source_root/"dist"
    verify_dist(dist,zip_name)
    previous={p.relative_to(output_root).as_posix():p for p in output_root.rglob("*") if p.is_file()} if output_root.exists() else {}
    # Inputs and prior outputs are completely checked before any mutation.
    output_root.mkdir(parents=True,exist_ok=True)
    for name,content in sorted(files.items(),key=lambda item:(item[0]=="build-manifest.json",item[0])):
        target=output_root/name; safe_tree(target); target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(content)
    for rel,file in previous.items():
        if rel not in files:
            if not file.resolve().is_relative_to(output_root.resolve()): fail("E_PATH_ESCAPE","过期生成文件越界。")
            file.unlink()
    dist=source_root/"dist"; safe_tree(dist); dist.mkdir(exist_ok=True)
    zip_bytes=make_zip(files); zip_name=f"16-minds-{identity['version']}-static_candidate.zip"
    (dist/zip_name).write_bytes(zip_bytes)
    (dist/"build-manifest.json").write_bytes(json_bytes({**manifest,"archive":{"file":zip_name,"sha256":digest(zip_bytes)}}))
    marketplace={"name":"16minds-local","interface":{"displayName":"16 Minds Local"},"plugins":[{"name":identity["name"],"source":{"source":"local","path":"./plugins/16-minds"},"policy":{"installation":"AVAILABLE","authentication":"ON_INSTALL"},"category":"Productivity"}]}
    # Candidate catalog: not registered. --marketplace writes the repo location explicitly.
    (dist/"marketplace.json").write_bytes(json_bytes(marketplace))
    return {"status":"ok","release_level":"static_candidate","file_count":len(files),"zip_file":"dist/"+zip_name,"zip_sha256":digest(zip_bytes)}

def main():
    if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true",help="compare generated package to source without changing files")
    parser.add_argument("--marketplace",action="store_true",help="write the repo-scoped candidate catalog; does not register/install")
    args=parser.parse_args()
    try:
        if args.check:
            identity,files,inputs=collect(ROOT); out=ROOT/"plugins/16-minds"; verify_existing(out)
            verify_dist(ROOT/"dist",f"16-minds-{identity['version']}-static_candidate.zip")
            current=strict_loads((out/"build-manifest.json").read_text("utf-8"))
            if current["source_hashes"]!=inputs or current["files"]!={k:digest(v) for k,v in sorted(files.items())}: fail("E_SEMANTIC","构建产物与当前维护源不一致。")
            result={"status":"ok","generated_matches_source":True}
        else: result=build()
        if args.marketplace:
            target=ROOT/".agents/plugins/marketplace.json"; safe_tree(target)
            if target.exists() and target.read_bytes()!=(ROOT/"dist/marketplace.json").read_bytes(): fail("E_EXISTS","已有不同 marketplace，拒绝覆盖。")
            target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes((ROOT/"dist/marketplace.json").read_bytes())
        print(json.dumps(result,ensure_ascii=False)); return 0
    except MindsError as exc:
        print(json.dumps(exc.as_dict(),ensure_ascii=False)); return exc.exit_code

if __name__=="__main__": raise SystemExit(main())
