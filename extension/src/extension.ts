import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { execFile, spawn } from 'child_process';

let setupComplete = false;

export function activate(context: vscode.ExtensionContext) {
	const extensionPath = context.extensionPath;
	const venvPath = path.join(extensionPath, '.venv');
	const isWindows = process.platform === 'win32';
	const pythonBin = isWindows
		? path.join(venvPath, 'Scripts', 'python.exe')
		: path.join(venvPath, 'bin', 'python3');

	ensureEnvironment(extensionPath, venvPath, pythonBin, isWindows);
}

function ensureEnvironment(extensionPath: string, venvPath: string, pythonBin: string, isWindows: boolean) {
	if (fs.existsSync(pythonBin)) {
		setupComplete = true;
		return;
	}

	// Find system Python
	const pythonCmd = isWindows ? 'python' : 'python3';

	// Create venv silently
	execFile(pythonCmd, ['-m', 'venv', venvPath], (err) => {
		if (err) {
			vscode.window.showErrorMessage(`azplex: Failed to create Python environment. Ensure Python 3.10+ is installed.`);
			return;
		}

		// Install mcp dependency into venv
		const pipBin = isWindows
			? path.join(venvPath, 'Scripts', 'pip.exe')
			: path.join(venvPath, 'bin', 'pip3');

		execFile(pipBin, ['install', '--quiet', 'mcp>=0.1.0'], (pipErr) => {
			if (pipErr) {
				vscode.window.showErrorMessage(`azplex: Failed to install dependencies. Check your network connection.`);
				return;
			}
			setupComplete = true;
		});
	});
}

export function deactivate() {}
