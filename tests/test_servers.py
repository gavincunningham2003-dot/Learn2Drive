import pandas as pd
import pytest

from file_receiver import recv_exact
from store_incidents import parse_ms_offset, read_csv_or_empty


class DribblingSocket:
    """Fake socket that hands back one byte per recv(), like a slow TCP link can."""

    def __init__(self, data):
        self.data = data

    def recv(self, n):
        chunk, self.data = self.data[:1], self.data[1:]
        return chunk


def test_recv_exact_reassembles_short_reads():
    sock = DribblingSocket(b"front_video.mp4")
    assert recv_exact(sock, 15) == b"front_video.mp4"


def test_recv_exact_raises_when_connection_closes_early():
    sock = DribblingSocket(b"abc")
    with pytest.raises(ConnectionError):
        recv_exact(sock, 10)


def test_parse_ms_offset_converts_seconds_to_timedelta():
    assert parse_ms_offset(1.5) == pd.Timedelta(milliseconds=1500)
    assert parse_ms_offset("2") == pd.Timedelta(seconds=2)


def test_parse_ms_offset_invalid_value_is_nat():
    assert pd.isna(parse_ms_offset("not a number"))
    assert pd.isna(parse_ms_offset(None))


def test_read_csv_or_empty_returns_expected_columns_when_file_missing(tmp_path):
    df = read_csv_or_empty(str(tmp_path / "nope.csv"), ["a", "b"])
    assert list(df.columns) == ["a", "b"]
    assert df.empty


def test_read_csv_or_empty_reads_existing_file(tmp_path):
    path = tmp_path / "events.csv"
    path.write_text("Departure_Time\n12.5\n")
    df = read_csv_or_empty(str(path), ["Departure_Time"])
    assert df["Departure_Time"].tolist() == [12.5]
