"""Locked source for the single-function Compact benchmark."""


def square(value: int) -> int:
    """Return the square of an integer."""
    raise NotImplementedError("implement square")


if __name__ == "__main__":
    from public_helper import square as implementation

    for argument, expected in ((0, 0), (3, 9), (-4, 16)):
        actual = implementation(argument)
        if actual != expected:
            raise AssertionError(
                f"square({argument}) returned {actual!r}, expected {expected}"
            )
