import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
	// azplex MCP server is contributed declaratively via package.json mcpServers.
	// This extension activates to ensure the MCP server entry is registered.
}

export function deactivate() {}
