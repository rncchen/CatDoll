@echo off
setlocal
pushd "%~dp0"

echo [1/2] Installing dependencies...
python -m pip install -r requirements.txt pyinstaller || goto :fail

echo [2/2] Building CatPet.exe...
python -m PyInstaller --onefile --windowed --name CatPet ^
    --add-data "catleft.png;." ^
    --add-data "catright.png;." ^
    --add-data "catsleep.png;." ^
    pet.py || goto :fail

echo.
echo Done. See dist\CatPet.exe
popd
endlocal
exit /b 0

:fail
echo Build failed.
popd
endlocal
exit /b 1
