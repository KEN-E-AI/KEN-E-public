import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { X, Upload, File, AlertTriangle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

export interface FileUploadProps {
  /** Array of accepted file extensions (e.g., ['.pdf', '.docx']) */
  accept?: string[];
  /** Whether to allow multiple files */
  multiple?: boolean;
  /** Maximum file size in bytes */
  maxSize?: number;
  /** Maximum total size across all files in bytes */
  maxTotalSize?: number;
  /** Maximum number of files */
  maxFiles?: number;
  /** Current files */
  files?: File[];
  /** Callback when files change */
  onFilesChange?: (files: File[]) => void;
  /** Custom validation function */
  validate?: (files: File[]) => string | null;
  /** Additional CSS classes */
  className?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Upload progress (0-100) */
  uploadProgress?: number;
  /** Whether upload is in progress */
  uploading?: boolean;
  /** Error message */
  error?: string;
}

export const FileUpload = React.forwardRef<HTMLDivElement, FileUploadProps>(
  (
    {
      accept = [
        ".pdf",
        ".xlsx",
        ".docx",
        ".pptx",
        ".txt",
        ".png",
        ".jpg",
        ".jpeg",
      ],
      multiple = true,
      maxSize = 25 * 1024 * 1024, // 25MB
      maxTotalSize = 100 * 1024 * 1024, // 100MB
      maxFiles = 10,
      files = [],
      onFilesChange,
      validate,
      className,
      disabled = false,
      uploadProgress,
      uploading = false,
      error,
      ...props
    },
    ref,
  ) => {
    const [dragActive, setDragActive] = React.useState(false);
    const [validationError, setValidationError] = React.useState<string | null>(
      null,
    );
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    const formatFileSize = (bytes: number): string => {
      if (bytes === 0) return "0 Bytes";
      const k = 1024;
      const sizes = ["Bytes", "KB", "MB", "GB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    };

    const validateFiles = (fileList: File[]): string | null => {
      // Check file count
      if (fileList.length > maxFiles) {
        return `Maximum ${maxFiles} files allowed`;
      }

      let totalSize = 0;
      for (const file of fileList) {
        // Check individual file size
        if (file.size > maxSize) {
          return `File "${file.name}" exceeds maximum size of ${formatFileSize(maxSize)}`;
        }

        // Check file extension
        const fileExt = "." + file.name.split(".").pop()?.toLowerCase();
        if (!accept.includes(fileExt)) {
          return `File type "${fileExt}" not allowed. Supported types: ${accept.join(", ")}`;
        }

        totalSize += file.size;
      }

      // Check total size
      if (totalSize > maxTotalSize) {
        return `Total file size exceeds ${formatFileSize(maxTotalSize)} limit`;
      }

      // Custom validation
      if (validate) {
        return validate(fileList);
      }

      return null;
    };

    const handleFiles = (fileList: FileList | null) => {
      if (!fileList || disabled) return;

      const newFiles = Array.from(fileList);
      const combinedFiles = multiple ? [...files, ...newFiles] : newFiles;

      const error = validateFiles(combinedFiles);
      setValidationError(error);

      if (!error) {
        onFilesChange?.(combinedFiles);
      }
    };

    const handleDrag = (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled) {
        if (e.type === "dragenter" || e.type === "dragover") {
          setDragActive(true);
        } else if (e.type === "dragleave") {
          setDragActive(false);
        }
      }
    };

    const handleDrop = (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      if (!disabled) {
        handleFiles(e.dataTransfer.files);
      }
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      handleFiles(e.target.files);
      // Clear the input value so the same file can be selected again
      if (e.target) {
        e.target.value = "";
      }
    };

    const removeFile = (index: number) => {
      if (disabled) return;
      const newFiles = files.filter((_, i) => i !== index);
      onFilesChange?.(newFiles);
      setValidationError(null);
    };

    const openFileDialog = () => {
      if (!disabled && fileInputRef.current) {
        fileInputRef.current.click();
      }
    };

    const displayError = error || validationError;
    const totalSize = files.reduce((sum, file) => sum + file.size, 0);

    return (
      <div ref={ref} className={cn("space-y-4", className)} {...props}>
        {/* Drop Zone */}
        <Card
          className={cn(
            "border-2 border-dashed transition-colors",
            dragActive &&
              !disabled &&
              "border-brand-medium-blue bg-brand-light-blue/10",
            disabled && "opacity-50 cursor-not-allowed",
            !disabled && "cursor-pointer hover:border-brand-medium-blue/50",
          )}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={openFileDialog}
        >
          <CardContent className="flex flex-col items-center justify-center py-8 text-center">
            <Upload className="h-10 w-10 text-dashboard-gray-400 mb-4" />
            <div className="space-y-2">
              <p className="text-sm font-medium text-dashboard-gray-700">
                {dragActive
                  ? "Drop files here"
                  : "Click to upload or drag and drop"}
              </p>
              <p className="text-xs text-dashboard-gray-500">
                Supported formats: {accept.join(", ")}
              </p>
              <p className="text-xs text-dashboard-gray-500">
                Max {formatFileSize(maxSize)} per file,{" "}
                {formatFileSize(maxTotalSize)} total, up to {maxFiles} files
              </p>
            </div>
          </CardContent>
        </Card>

        <input
          ref={fileInputRef}
          type="file"
          multiple={multiple}
          accept={accept.join(",")}
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled}
        />

        {/* Upload Progress */}
        {uploading && typeof uploadProgress === "number" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-dashboard-gray-600">Uploading...</span>
              <span className="text-dashboard-gray-600">{uploadProgress}%</span>
            </div>
            <Progress value={uploadProgress} className="h-2" />
          </div>
        )}

        {/* Error Display */}
        {displayError && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{displayError}</AlertDescription>
          </Alert>
        )}

        {/* File List */}
        {files.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-dashboard-gray-700">
              Selected Files ({files.length}/{maxFiles})
            </h4>
            <div className="space-y-2">
              {files.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="flex items-center justify-between p-3 bg-dashboard-gray-50 rounded-lg"
                >
                  <div className="flex items-center space-x-3">
                    <File className="h-4 w-4 text-dashboard-gray-400" />
                    <div>
                      <p className="text-sm font-medium text-dashboard-gray-700">
                        {file.name}
                      </p>
                      <p className="text-xs text-dashboard-gray-500">
                        {formatFileSize(file.size)}
                      </p>
                    </div>
                  </div>
                  {!disabled && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(index);
                      }}
                      className="h-8 w-8 p-0"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>

            {/* Total Size */}
            <div className="flex justify-between text-xs text-dashboard-gray-500">
              <span>Total size: {formatFileSize(totalSize)}</span>
              <span>{formatFileSize(maxTotalSize - totalSize)} remaining</span>
            </div>
          </div>
        )}
      </div>
    );
  },
);

FileUpload.displayName = "FileUpload";
