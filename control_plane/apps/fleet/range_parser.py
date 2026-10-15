import re


def expand_host_range(pattern: str) -> list[str]:
    """
    Expands bracketed range patterns into a list of discrete hostnames.
    Examples:
        'compute-[01:05].internal' -> ['compute-01.internal', 'compute-02.internal', ...]
        'node-[1:3],gpu-[08:10]' -> ['node-1', 'node-2', 'node-3', 'gpu-08', 'gpu-09', 'gpu-10']
    """
    if not pattern or not isinstance(pattern, str):
        return []

    tokens = [t.strip() for t in pattern.split(",") if t.strip()]
    results: list[str] = []

    # Regex matching bracketed range: prefix[start:end]suffix
    range_regex = re.compile(r"^(?P<prefix>.*?)\[(?P<start>\d+):(?P<end>\d+)\](?P<suffix>.*)$")

    for token in tokens:
        match = range_regex.match(token)
        if match:
            prefix = match.group("prefix")
            start_str = match.group("start")
            end_str = match.group("end")
            suffix = match.group("suffix")

            start = int(start_str)
            end = int(end_str)

            if start > end:
                raise ValueError(f"Invalid range bounds in '{token}': start {start} > end {end}")

            pad_length = len(start_str) if (start_str.startswith("0") and len(start_str) > 1) else 0

            for num in range(start, end + 1):
                if pad_length > 0:
                    num_str = str(num).zfill(pad_length)
                else:
                    num_str = str(num)
                host = f"{prefix}{num_str}{suffix}"
                if host not in results:
                    results.append(host)
        else:
            if token not in results:
                results.append(token)

    return results
