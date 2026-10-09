const LIVE_API = "https://fcz6jcdep5ykiv5st7aq7az3mq0jkjfn.lambda-url.ap-south-1.on.aws";

const trim = (url: string) => url.replace(/\/+$/, "");

export const API_URL = trim(import.meta.env.VITE_API_URL || LIVE_API);
export const CHAT_URL = trim(import.meta.env.VITE_CHAT_URL || API_URL);

/** Languages with a full UI translation. */
export const UI_LANGS = ["en", "hi"] as const;
/** Languages Amazon Polly can read aloud (Kajal neural). */
export const SPEAK_LANGS = ["en", "hi"] as const;

export const MAX_UPLOAD_BYTES = 8 * 1024 * 1024;
