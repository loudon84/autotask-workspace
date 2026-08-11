import {
  getEndpointConfig,
  getState,
  login,
  logout,
  refresh,
  saveEndpoint,
} from "./handlers";

export const auth = {
  getState,
  getEndpointConfig,
  saveEndpoint,
  login,
  logout,
  refresh,
};
