/*
 * fast_click.c - Windows快速点击DLL
 * 通过Windows API实现快速鼠标操作，绕过UI Automation的延迟
 * 编译: cl /LD fast_click.c user32.lib /Fe:fast_click.dll
 * 或: gcc -shared -o fast_click.dll fast_click.c -luser32
 */

#include <windows.h>

/* 快速鼠标点击 */
__declspec(dllexport) int fast_click(int x, int y) {
    SetCursorPos(x, y);
    Sleep(10);

    INPUT inputs[2];
    ZeroMemory(inputs, sizeof(inputs));

    inputs[0].type = INPUT_MOUSE;
    inputs[0].mi.dwFlags = MOUSEEVENTF_LEFTDOWN;

    inputs[1].type = INPUT_MOUSE;
    inputs[1].mi.dwFlags = MOUSEEVENTF_LEFTUP;

    UINT sent = SendInput(2, inputs, sizeof(INPUT));
    return (sent == 2) ? 0 : -1;
}

/* 快速双击 */
__declspec(dllexport) int fast_double_click(int x, int y) {
    int r1 = fast_click(x, y);
    Sleep(50);
    int r2 = fast_click(x, y);
    return (r1 == 0 && r2 == 0) ? 0 : -1;
}

/* 查找微信主窗口 */
__declspec(dllexport) HWND find_wechat_window(void) {
    return FindWindowW(L"WeChatMainWndForPC", NULL);
}

/* 窗口置顶 */
__declspec(dllexport) int bring_to_front(HWND hwnd) {
    if (!IsWindow(hwnd)) return -1;

    if (IsIconic(hwnd)) {
        ShowWindow(hwnd, SW_RESTORE);
    }

    SetForegroundWindow(hwnd);
    BringWindowToTop(hwnd);
    return 0;
}

/* 后台点击（不激活窗口） */
__declspec(dllexport) int background_click(HWND hwnd, int x, int y) {
    if (!IsWindow(hwnd)) return -1;

    LPARAM lParam = MAKELPARAM(x, y);
    PostMessage(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam);
    Sleep(30);
    PostMessage(hwnd, WM_LBUTTONUP, 0, lParam);
    return 0;
}

#ifdef BUILD_TEST
/* 测试入口 */
int main(void) {
    HWND hwnd = find_wechat_window();
    if (hwnd) {
        printf("Found WeChat window: %p\n", (void*)hwnd);
        bring_to_front(hwnd);
    } else {
        printf("WeChat window not found.\n");
    }
    return 0;
}
#endif
