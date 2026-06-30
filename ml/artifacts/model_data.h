#ifndef MODEL_DATA_H
#define MODEL_DATA_H
#include <stdint.h>
#define MODEL_N_FEATURES 38
extern const unsigned char g_model_int8[];
extern const unsigned int g_model_int8_len;
extern const float g_feat_mean[MODEL_N_FEATURES];
extern const float g_feat_std[MODEL_N_FEATURES];
#endif
