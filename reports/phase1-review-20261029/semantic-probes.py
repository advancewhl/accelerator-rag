"""Small read-only checks of claims in the Phase 1 documents.

Run with the waveform-storage Python environment. Source repositories, services,
and indexes are not modified. Temporary HDF5 outputs are removed on exit.
"""

import json
from pathlib import Path
import sys
import tempfile

import numpy as np

WAVEFORM = Path('/home/whloong/waveform-storage/waveform-storage-system')
sys.path.insert(0, str(WAVEFORM / 'src'))
from waveform_storage.processing.alignment import (
    AlignmentParameters, DeviceSeries, align_devices,
)
from waveform_storage.io.hdf5_io import write_legacy_merged_hdf5
from waveform_storage.analysis.loaders import _id_times, _waveform_series
from waveform_storage.analysis.engine import _prepare
from waveform_storage.analysis.models import AnalysisConfig, ChannelResult


def device(name, ids):
    return DeviceSeries(name, np.array(ids, dtype=np.uint64),
                        np.arange(len(ids), dtype=np.int64),
                        np.arange(len(ids), dtype=np.int64) + 1)


rows = {}
different = align_devices([device('A', [2, 4, 6]), device('B', [2, 6, 10])])
rows['different_steps_can_intersect'] = different.bunch_ids.tolist()
rows['zero_keep_vs_drop'] = {
    policy: align_devices([device('A', [0, 2, 4]), device('B', [2, 4])],
                          AlignmentParameters(zero_policy=policy)).bunch_ids.tolist()
    for policy in ('keep', 'drop')
}
covered = align_devices([device('A', [1, 2, 3]), device('B', [1, 2, 3])],
                        AlignmentParameters(mode='coverage'))
with tempfile.TemporaryDirectory(prefix='phase1-review-') as tmp:
    path = Path(tmp) / 'coverage-legacy.h5'
    write_legacy_merged_hdf5(path, covered)
    rows['coverage_without_missing_can_write_legacy'] = {
        'all_valid': bool(covered.valid_mask.all()), 'written': path.is_file(),
    }

ids = np.array([100, 200, 300, 400, 500, 600], dtype=np.uint64)
values = np.array([[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]])
mask = np.array([[True] * 6, [False, True, True, True, True, True]])
config = AnalysisConfig(search_low_hz=1, search_high_hz=2,
                        background_low_hz=.5, background_high_hz=3,
                        minimum_points=4, minimum_seconds=.1)
rows['coverage_channel_time_origin'] = []
for series in _waveform_series(ids, values, values + 1, ('A', 'B'),
                               'synthetic audit example', 10, 'file_metadata', mask):
    if series.channel.endswith('_X'):
        result = ChannelResult(series.channel, series.source)
        grid, _, _ = _prepare(series, config, result)
        rows['coverage_channel_time_origin'].append({
            'channel': series.channel,
            'loader_first_time': float(series.times[0]),
            'engine_first_valid_offset': result.quality['first_valid_offset_seconds'],
            'engine_first_time': float(grid[0]),
            'engine_duration': result.duration_seconds,
        })

rows['historical_fixture_time_axis'] = []
fixture_dir = WAVEFORM / 'outputs/history-ui-validation-20261016/bunch-id-fixtures'
request = '22833275-5e77-41c5-b703-f306accde164'
for seq in range(5):
    with np.load(fixture_dir / f'{request}_S{seq:05d}.npz', allow_pickle=True) as data:
        devices = json.loads(str(data['device_ids_json']))
        arrays = [data[f'bunch_ids_{i:02d}'] for i in range(len(devices))]
        common = arrays[0]
        for array in arrays[1:]:
            common = np.intersect1d(common, array)
        row = {'sequence': seq, 'points': len(common),
               'array_equal_to_recorded': bool(np.array_equal(common, data['common_bunch_ids'])),
               'point_count_estimate_seconds': (len(common) - 1) / 500}
        try:
            times, step = _id_times(common, 500)
        except ValueError as exc:
            row['actual_loader_error'] = str(exc)
        else:
            row.update(actual_loader_duration_seconds=float(times[-1]), modal_step=step)
        rows['historical_fixture_time_axis'].append(row)

print(json.dumps(rows, ensure_ascii=False, indent=2))
