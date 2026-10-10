// Shared class names: one accent colour, neutral greys, CSS transitions of 150 ms.

export const button = {
  primary:
    "inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 font-medium text-white " +
    "transition-colors duration-150 hover:bg-accent-strong disabled:cursor-not-allowed " +
    "disabled:opacity-50",
  secondary:
    "inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2 " +
    "font-medium text-gray-800 transition-colors duration-150 hover:bg-gray-50 " +
    "disabled:cursor-not-allowed disabled:opacity-50",
};

export const input =
  "w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 " +
  "transition-colors duration-150 hover:border-gray-400 focus:border-accent";

export const card = "rounded-lg border border-gray-200 bg-white p-5";

export const table = "w-full border-collapse text-left text-sm";
export const th = "border-b border-gray-200 px-3 py-2 font-medium text-gray-600";
export const td = "border-b border-gray-100 px-3 py-2 align-top";
