/**
 * Utility class for building FormData with consistent JSON serialization.
 * This ensures all array fields are properly serialized as JSON strings.
 */
export class FormDataBuilder {
  private formData: FormData;

  constructor() {
    this.formData = new FormData();
  }

  /**
   * Append a field to the FormData.
   * Arrays are automatically JSON.stringified.
   * Null/undefined values are skipped.
   */
  append(key: string, value: any): this {
    if (value === null || value === undefined) {
      return this;
    }

    if (Array.isArray(value)) {
      this.formData.append(key, JSON.stringify(value));
    } else if (typeof value === "object" && !(value instanceof File)) {
      // For non-File objects, stringify them
      this.formData.append(key, JSON.stringify(value));
    } else if (typeof value === "number") {
      this.formData.append(key, value.toString());
    } else if (typeof value === "boolean") {
      this.formData.append(key, value.toString());
    } else {
      // String, File, or other types
      this.formData.append(key, value);
    }

    return this;
  }

  /**
   * Append multiple files to the FormData.
   */
  appendFiles(key: string, files: File[]): this {
    files.forEach((file) => {
      this.formData.append(key, file);
    });
    return this;
  }

  /**
   * Build an object from key-value pairs and append all fields.
   */
  appendObject(obj: Record<string, any>): this {
    Object.entries(obj).forEach(([key, value]) => {
      this.append(key, value);
    });
    return this;
  }

  /**
   * Get the built FormData instance.
   */
  build(): FormData {
    return this.formData;
  }

  /**
   * Static helper to quickly build FormData from an object.
   */
  static fromObject(obj: Record<string, any>): FormData {
    const builder = new FormDataBuilder();
    return builder.appendObject(obj).build();
  }
}