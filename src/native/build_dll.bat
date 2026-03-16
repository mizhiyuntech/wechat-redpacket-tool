@echo off
REM DLL编译脚本 - 使用MSVC或MinGW编译fast_click.dll
REM 方式1: MSVC (需要Visual Studio)
REM cl /LD fast_click.c user32.lib /Fe:fast_click.dll
REM 方式2: MinGW-w64
REM gcc -shared -o fast_click.dll fast_click.c -luser32

echo 正在编译 fast_click.dll ...

where gcc >nul 2>nul
if %ERRORLEVEL% == 0 (
    echo 使用 GCC 编译...
    gcc -shared -O2 -o fast_click.dll fast_click.c -luser32
    if %ERRORLEVEL% == 0 (
        echo 编译成功: fast_click.dll
    ) else (
        echo GCC 编译失败
        goto :try_msvc
    )
    goto :done
)

:try_msvc
where cl >nul 2>nul
if %ERRORLEVEL% == 0 (
    echo 使用 MSVC 编译...
    cl /LD /O2 fast_click.c user32.lib /Fe:fast_click.dll
    if %ERRORLEVEL% == 0 (
        echo 编译成功: fast_click.dll
    ) else (
        echo MSVC 编译失败
        goto :error
    )
    goto :done
)

:error
echo 错误: 未找到 GCC 或 MSVC 编译器
echo 请安装 MinGW-w64 或 Visual Studio Build Tools
exit /b 1

:done
echo 完成
