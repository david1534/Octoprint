<script lang="ts">
	import { api } from '../api';
	import { currentPath, refreshFiles } from '../stores/files';
	import { toast } from '../stores/toast';
	import { formatFileSize } from '../utils';

	let dragging = $state(false);
	let uploading = $state(false);
	let uploadProgress = $state(0);
	let uploadFilename = $state('');
	let uploadedBytes = $state(0);
	let totalBytes = $state(0);

	async function handleFiles(fileList: FileList | null) {
		if (!fileList || fileList.length === 0) return;
		uploading = true;
		uploadProgress = 0;

		try {
			const names: string[] = [];
			for (const file of Array.from(fileList)) {
				uploadFilename = file.name;
				totalBytes = file.size;
				uploadedBytes = 0;
				uploadProgress = 0;

				await uploadWithProgress(file);
				names.push(file.name);
			}
			await refreshFiles($currentPath);
			toast.success(`Uploaded: ${names.join(', ')}`);
		} catch (e: any) {
			toast.error(e.message || 'Upload failed');
		} finally {
			uploading = false;
			uploadProgress = 0;
			uploadFilename = '';
		}
	}

	function uploadWithProgress(file: File): Promise<void> {
		return new Promise((resolve, reject) => {
			const xhr = new XMLHttpRequest();
			const formData = new FormData();
			formData.append('file', file);

			xhr.upload.addEventListener('progress', (e) => {
				if (e.lengthComputable) {
					uploadProgress = Math.round((e.loaded / e.total) * 100);
					uploadedBytes = e.loaded;
				}
			});

			xhr.addEventListener('load', () => {
				if (xhr.status >= 200 && xhr.status < 300) {
					resolve();
				} else {
					try {
						const err = JSON.parse(xhr.responseText);
						reject(new Error(err.detail || `Upload failed: ${xhr.status}`));
					} catch {
						reject(new Error(`Upload failed: ${xhr.status}`));
					}
				}
			});

			xhr.addEventListener('error', () => reject(new Error('Upload failed: network error')));
			xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));

			const params = $currentPath ? `?path=${encodeURIComponent($currentPath)}` : '';
			xhr.open('POST', `/api/files/upload${params}`);
			// Include auth header — without this, uploads fail 401 when API key is set
			const apiKey = typeof localStorage !== 'undefined' ? localStorage.getItem('printforge:apiKey') : null;
			if (apiKey) xhr.setRequestHeader('Authorization', `Bearer ${apiKey}`);
			xhr.send(formData);
		});
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragging = false;
		handleFiles(e.dataTransfer?.files ?? null);
	}

	function onDragOver(e: DragEvent) {
		e.preventDefault();
		dragging = true;
	}

	function onDragLeave() {
		dragging = false;
	}

	function onInputChange(e: Event) {
		const input = e.target as HTMLInputElement;
		handleFiles(input.files);
		input.value = '';
	}
</script>

<div
	class="border-2 border-dashed rounded-xl p-6 text-center transition-colors
		   {dragging ? 'border-accent bg-accent/5' : 'border-surface-700 hover:border-surface-500'}
		   {uploading ? 'cursor-wait' : ''}"
	ondrop={onDrop}
	ondragover={onDragOver}
	ondragleave={onDragLeave}
	role="button"
	tabindex="0"
>
	{#if uploading}
		<div class="max-w-xs mx-auto">
			<svg class="w-8 h-8 mx-auto mb-2 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
			</svg>
			<p class="text-sm text-surface-300 font-medium mb-1 truncate">{uploadFilename}</p>
			<div class="w-full h-2 bg-surface-800 rounded-full overflow-hidden mb-1.5">
				<div
					class="h-full rounded-full bg-accent transition-all duration-300"
					style="width: {uploadProgress}%"
				></div>
			</div>
			<p class="text-xs text-surface-500 tabular-nums">
				{uploadProgress}% - {formatFileSize(uploadedBytes)} / {formatFileSize(totalBytes)}
			</p>
		</div>
	{:else}
		<svg class="w-10 h-10 mx-auto mb-2 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
		</svg>
		<p class="text-sm text-surface-400 mb-1">Drop G-code files here or</p>
		<label class="btn-primary text-sm cursor-pointer inline-block">
			Browse
			<input type="file" class="hidden" accept=".gcode,.g,.gc" multiple onchange={onInputChange} />
		</label>
	{/if}
</div>
