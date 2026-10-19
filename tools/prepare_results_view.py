import argparse,csv,json,math
from pathlib import Path

FIELDS=[
    'analysis','measure','value',
    'sample_size','notes'
]

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()

    inp=a.input.resolve()
    out=a.output.resolve()
    home=Path(__file__).resolve().parent.parent

    if (
        not inp.is_file()
        or out.exists()
        or out==home
        or home in out.parents
    ):
        raise ValueError(
            'Input missing or output must be NEW and private'
        )

    with inp.open(newline='',encoding='utf-8-sig') as f:
        r=csv.DictReader(f)

        if r.fieldnames!=FIELDS:
            raise ValueError('Aggregate columns differ')

        rows=list(r)

    if not rows:
        raise ValueError('Empty aggregate results')

    for row in rows:
        if (
            None in row
            or not row['analysis']
            or not row['measure']
        ):
            raise ValueError('Invalid aggregate result')

        if (
            not math.isfinite(float(row['value']))
            or int(row['sample_size'])<0
        ):
            raise ValueError('Invalid aggregate metric')

        for k in ('analysis','measure','notes'):
            s=row[k] or ''

            if (
                len(s)>1000
                or (bool(s) and s[0] in '=+-@')
                or any(ch in s for ch in '\r\n\t')
            ):
                raise ValueError('Unsafe Excel text')

    out.mkdir(parents=True)

    with (
        out/'RESULTS_VIEW_PASTE_NO_HEADER.tsv'
    ).open('x',newline='') as f:
        w=csv.writer(
            f,delimiter='\t',lineterminator='\n'
        )
        w.writerows(
            [[row[k] for k in FIELDS] for row in rows]
        )

    (out/'VIEW_REPORT.json').write_text(
        json.dumps({
            'aggregate_rows':len(rows),
            'native_excel_recalculation_verified':False,
            'publication_authorized':False
        },indent=2)+'\n'
    )

    print(
        'PASS |',len(rows),
        'Excel aggregate rows. '
        'Paste VALUES at RESULTS VIEW!A4 after clearing A5.'
    )
