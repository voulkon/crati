@echo off
set result=
for /r %%F in (*.py) do (
    if not "%%F" == "" (
        echo %%F | findstr /v "__pycache__\|\.git\|venv" >> %TEMP%\pytree.txt
    )
)
type %TEMP%\pytree.txt | clip
echo Python files copied to clipboard!
del %TEMP%\pytree.txt