"""Join separate scientific category JSONs without altering terrain ranking features.

python prep/merge_mars.py --terrain data/jezero_features.json \\
  --parts-dir data/parts/jezero_01 --output data/combined/jezero_01.json
"""
import argparse
import json
from pathlib import Path

CATEGORIES = ('geology','minerals','thermal','albedo','dust','wind')


def merge(terrain_file, parts_dir):
    terrain = json.loads(Path(terrain_file).read_text(encoding='utf-8'))
    site_id = terrain['id']
    result = {'location_id':site_id, 'name':terrain.get('name'), 'terrain':terrain,
              'modules':{}, 'missing_modules':[]}
    for category in CATEGORIES:
        file = Path(parts_dir) / f'{category}.json'
        if not file.exists():
            result['missing_modules'].append(category)
            continue
        payload = json.loads(file.read_text(encoding='utf-8'))
        if payload.get('location_id') != site_id or payload.get('category') != category:
            raise ValueError(f'Wrong site ID or category in {file}')
        result['modules'][category] = payload
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--terrain', required=True)
    p.add_argument('--parts-dir', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    result = merge(args.terrain, args.parts_dir)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(f'Saved {out}; modules: {list(result["modules"])}; missing: {result["missing_modules"]}')

if __name__ == '__main__':
    main()
