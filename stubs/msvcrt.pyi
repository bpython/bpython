# The real types seem only available on the Windows platform,
# but it seems annoying to need to run typechecking once per platform
# https://github.com/python/typeshed/blob/master/stdlib/msvcrt.pyi
def locking(__fd: int, __mode: int, __nbytes: int) -> None: ...

LK_NBLCK: int
LK_UNLCK: int
