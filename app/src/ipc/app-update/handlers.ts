import { os } from "@orpc/server";
import { appUpdater } from "@/main/app-updater";

export const getState = os.handler(() => appUpdater.getState());

export const check = os.handler(() => appUpdater.check());

export const download = os.handler(() => appUpdater.download());

export const downloadAndInstall = os.handler(() => appUpdater.downloadAndInstall());

export const install = os.handler(() => appUpdater.install());
