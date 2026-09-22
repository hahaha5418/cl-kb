// CL 的 AI 知识库 —— 桌面版入口
// 纯静态站点打包：不需要任何 Tauri 命令，只加载内置的 VitePress 产物
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("CL-AI-KB 启动失败");
}
